// Package tsbridge mette un nodo Tailscale dentro l'app NEXUS (telefono e orologio) con tsnet:
// niente VPN di sistema, niente app Tailscale. L'app usa un proxy HTTP locale (127.0.0.1) che
// esce dalla rete Tailscale, quindi raggiunge il PC di casa (100.x.y.z) da Wi-Fi o LTE.
//
// Compilato con gomobile bind (vedi .github/workflows/tsbridge.yml).
package tsbridge

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/netip"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"tailscale.com/ipn"
	"tailscale.com/net/netmon"
	"tailscale.com/tsnet"
)

var (
	mu       sync.Mutex
	srv      *tsnet.Server
	proxyLn  net.Listener
	lastErr  string
	ifaceStr string // interfacce di rete passate da Kotlin (Android non lascia leggerle con netlink)
)

// SetInterfaces riceve le interfacce di rete da Android, una per riga:
// "nome index mtu up loopback indirizzo/prefisso,indirizzo/prefisso"
func SetInterfaces(s string) {
	mu.Lock()
	ifaceStr = s
	mu.Unlock()
}

func androidInterfaces() ([]netmon.Interface, error) {
	mu.Lock()
	s := ifaceStr
	mu.Unlock()
	var out []netmon.Interface
	for _, line := range strings.Split(strings.TrimSpace(s), "\n") {
		f := strings.Fields(line)
		if len(f) < 5 {
			continue
		}
		idx, _ := strconv.Atoi(f[1])
		mtu, _ := strconv.Atoi(f[2])
		var flags net.Flags
		if f[3] == "1" {
			flags |= net.FlagUp | net.FlagRunning
		}
		if f[4] == "1" {
			flags |= net.FlagLoopback
		} else {
			flags |= net.FlagBroadcast | net.FlagMulticast
		}
		ni := &net.Interface{Index: idx, MTU: mtu, Name: f[0], Flags: flags}
		var addrs []net.Addr
		if len(f) > 5 {
			for _, a := range strings.Split(f[5], ",") {
				if p, err := netip.ParsePrefix(a); err == nil {
					addrs = append(addrs, &net.IPNet{IP: p.Addr().AsSlice(), Mask: net.CIDRMask(p.Bits(), p.Addr().BitLen())})
				}
			}
		}
		out = append(out, netmon.Interface{Interface: ni, AltAddrs: addrs})
	}
	return out, nil
}

// Start accende il nodo. dir: cartella privata dell'app (lì resta la chiave del nodo, così resta collegato).
// authKey può essere vuota: allora serve il login dal link (Status().authURL).
func Start(dir, hostname, authKey string) error {
	mu.Lock()
	defer mu.Unlock()
	if srv != nil {
		return nil
	}
	os.Setenv("TS_NO_LOGS_NO_SUPPORT", "true") // niente log inviati a Tailscale
	netmon.RegisterInterfaceGetter(androidInterfaces)
	s := &tsnet.Server{Dir: dir, Hostname: hostname, AuthKey: authKey, Logf: func(string, ...any) {}}
	if err := s.Start(); err != nil {
		lastErr = err.Error()
		return err
	}
	srv = s
	lastErr = ""
	return nil
}

type status struct {
	State   string   `json:"state"`   // Spento | NeedsLogin | Starting | Running | NeedsMachineAuth | errore
	AuthURL string   `json:"authURL"` // link per collegare il dispositivo (login)
	IPs     []string `json:"ips"`
	Name    string   `json:"name"`
	Tailnet string   `json:"tailnet"`
	Error   string   `json:"error"`
}

// Status ritorna lo stato in JSON.
func Status() string {
	mu.Lock()
	s := srv
	e := lastErr
	mu.Unlock()
	st := status{State: "Spento", Error: e}
	if s != nil {
		if lc, err := s.LocalClient(); err == nil {
			ctx, cancel := context.WithTimeout(context.Background(), 4*time.Second)
			defer cancel()
			if ps, err := lc.StatusWithoutPeers(ctx); err == nil {
				st.State = ps.BackendState
				st.AuthURL = ps.AuthURL
				for _, ip := range ps.TailscaleIPs {
					st.IPs = append(st.IPs, ip.String())
				}
				if ps.Self != nil {
					st.Name = strings.TrimSuffix(ps.Self.DNSName, ".")
				}
				if ps.CurrentTailnet != nil {
					st.Tailnet = ps.CurrentTailnet.Name
				}
				if st.State == ipn.NeedsLogin.String() && st.AuthURL == "" {
					// chiede un link di login nuovo
					go lc.StartLoginInteractive(context.Background())
				}
			} else {
				st.Error = err.Error()
			}
		}
	}
	b, _ := json.Marshal(st)
	return string(b)
}

// ProxyPort avvia (una volta) un proxy HTTP su 127.0.0.1 che esce dalla rete Tailscale e ne ritorna la porta.
func ProxyPort() (int, error) {
	mu.Lock()
	defer mu.Unlock()
	if srv == nil {
		return 0, fmt.Errorf("tailscale non è acceso")
	}
	if proxyLn != nil {
		return proxyLn.Addr().(*net.TCPAddr).Port, nil
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	proxyLn = ln
	s := srv
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go handle(s, c)
		}
	}()
	return ln.Addr().(*net.TCPAddr).Port, nil
}

func handle(s *tsnet.Server, c net.Conn) {
	defer c.Close()
	br := bufio.NewReader(c)
	req, err := http.ReadRequest(br)
	if err != nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	if req.Method == http.MethodConnect { // HTTPS (o qualsiasi TCP): tunnel
		up, err := s.Dial(ctx, "tcp", req.Host)
		if err != nil {
			fmt.Fprintf(c, "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
			return
		}
		defer up.Close()
		fmt.Fprintf(c, "HTTP/1.1 200 Connection established\r\n\r\n")
		go io.Copy(up, br)
		io.Copy(c, up)
		return
	}
	// HTTP in chiaro: inoltra la richiesta così com'è
	host := req.Host
	if !strings.Contains(host, ":") {
		host += ":80"
	}
	up, err := s.Dial(ctx, "tcp", host)
	if err != nil {
		fmt.Fprintf(c, "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
		return
	}
	defer up.Close()
	req.RequestURI = ""
	req.URL.Scheme = ""
	req.URL.Host = ""
	req.Header.Del("Proxy-Connection")
	req.Header.Set("Connection", "close")
	if err := req.Write(up); err != nil {
		return
	}
	io.Copy(c, up)
}

// Logout scollega il dispositivo da Tailscale (al prossimo avvio servirà un nuovo login).
func Logout() {
	mu.Lock()
	s := srv
	mu.Unlock()
	if s == nil {
		return
	}
	if lc, err := s.LocalClient(); err == nil {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		lc.Logout(ctx)
	}
}

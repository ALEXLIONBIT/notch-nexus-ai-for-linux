import QtQuick
import QtQuick.Particles
import QtQuick.Shapes

// Effetti di sfondo dei temi: neve a Natale, pipistrelli a Halloween.
Item {
    id: deco
    required property var store
    readonly property string kind: store.th.deco

    // ---------- neve ----------
    ParticleSystem {
        id: snow
        anchors.fill: parent
        running: deco.kind === "natale" && deco.visible
    }
    ImageParticle {
        system: snow
        source: "qrc:///particleresources/glowdot.png"
        color: "#ffffff"; colorVariation: 0.05
        alpha: 0.85
        entryEffect: ImageParticle.Fade
    }
    Emitter {
        system: snow
        enabled: deco.kind === "natale"
        width: parent.width; height: 1; y: -20
        emitRate: 45; lifeSpan: 14000
        size: 14; sizeVariation: 12
        velocity: PointDirection { y: 70; yVariation: 40; xVariation: 25 }
    }
    Wander { system: snow; anchors.fill: parent; xVariance: 60; pace: 40 }

    // ---------- pipistrelli ----------
    Repeater {
        model: deco.kind === "halloween" ? 6 : 0
        Item {
            id: bat
            property real speed: 9000 + index * 2300
            property real baseY: 60 + index * deco.height * 0.12
            property real flap: 0
            width: 90 - index * 8; height: width * 0.5
            property real p: 0
            NumberAnimation on p { from: 0; to: 1; duration: bat.speed; loops: Animation.Infinite; running: deco.visible }
            readonly property real fx: -140 + (deco.width + 280) * (index % 2 ? 1 - p : p)
            x: fx
            y: baseY + Math.sin(fx / 90) * 30
            SequentialAnimation on flap { loops: Animation.Infinite; running: deco.visible
                NumberAnimation { to: 1; duration: 140 + index * 20 }
                NumberAnimation { to: 0; duration: 140 + index * 20 } }
            transform: Scale { origin.x: bat.width / 2; yScale: 1 - bat.flap * 0.5; xScale: index % 2 ? -1 : 1 }
            Shape {
                anchors.fill: parent
                ShapePath {
                    fillColor: "#07030c"; strokeWidth: -1
                    startX: bat.width * 0.5; startY: bat.height * 0.35
                    PathQuad { x: 0; y: bat.height * 0.2; controlX: bat.width * 0.22; controlY: -bat.height * 0.1 }
                    PathQuad { x: bat.width * 0.18; y: bat.height * 0.7; controlX: bat.width * 0.02; controlY: bat.height * 0.55 }
                    PathQuad { x: bat.width * 0.5; y: bat.height * 0.95; controlX: bat.width * 0.35; controlY: bat.height * 0.6 }
                    PathQuad { x: bat.width * 0.82; y: bat.height * 0.7; controlX: bat.width * 0.65; controlY: bat.height * 0.6 }
                    PathQuad { x: bat.width; y: bat.height * 0.2; controlX: bat.width * 0.98; controlY: bat.height * 0.55 }
                    PathQuad { x: bat.width * 0.5; y: bat.height * 0.35; controlX: bat.width * 0.78; controlY: -bat.height * 0.1 }
                }
            }
            Repeater {   // occhietti
                model: 2
                Rectangle { width: 3; height: 3; radius: 1.5; color: "#ffb02e"
                    x: bat.width * (0.46 + index * 0.06); y: bat.height * 0.42 }
            }
        }
    }
}

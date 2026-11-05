"""Draw the original DataGuard field journal plates as compact standalone SVGs."""

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dataguard"
ART = ROOT / "archive-art"
W, H = 640, 440
INK = "#254332"
GOLD = "#9d7738"
LIME = "#c7d44b"
FOLIO = "#f5ecd8"


def path(d, stroke=INK, width=1, fill="none", opacity=1):
    attributes = [f'd="{d}"']
    for name, value, default in (
        ("fill", fill, "none"),
        ("stroke", stroke, INK),
        ("stroke-width", width, 1),
        ("opacity", opacity, 1),
    ):
        if value != default:
            attributes.append(f'{name}="{value}"')
    return "<path " + " ".join(attributes) + "/>"


def line(x, y, x2, y2, color=INK, opacity=0.7):
    return path(f"M{x:g} {y:g}L{x2:g} {y2:g}", color, 0.8, opacity=opacity)


def ellipse(x, y, rx, ry, color=INK, fill="none", opacity=0.7):
    return f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" stroke="{color}" fill="{fill}" opacity="{opacity}"/>'


def group(drawing, transform):
    return f'<g transform="{transform}">{drawing}</g>'


def pts(points):
    return "L".join(f"{round(x)} {round(y)}" for x, y in points)


def leaf(x, y, angle, length, breadth, *, fill="url(#leaf)", divisions=18):
    """An etched pointed leaf, with a curved midrib and paired branching veins."""
    edge = []
    for side in (1, -1):
        for i in range(31):
            t = i / 30 if side == 1 else 1 - i / 30
            radius = breadth * math.sin(math.pi * t) ** 0.86
            edge.append((side * radius * (1 if i % 2 else 0.94) + 8 * t**2, -length * t))
    shell = path("M" + pts(edge) + "Z", INK, 1.35, fill)
    veins = [path(f"M-9 26Q-3 -{length * 0.35:.0f} 8 -{length}", INK, 1.45)]
    for i in range(1, divisions):
        t = i / divisions
        dist = breadth * math.sin(math.pi * t) ** 0.86
        for side in (-1, 1):
            a, b = side * dist, -length * t
            veins.append(
                path(
                    f"M{8 * t * t:.1f} {b + 13:.1f}Q{a * 0.54:.1f} {b + 9:.1f} {a + 8 * t * t:.1f} {b:.1f}",
                    INK,
                    0.62,
                    opacity=0.75,
                )
            )
            veins.append(
                path(
                    f"M{a * 0.45:.1f} {b + 7:.1f}L{a * 0.59:.1f} {b - 3:.1f}M{a * 0.64:.1f} {b + 4:.1f}L{a * 0.8:.1f} {b + 9:.1f}",
                    INK,
                    0.45,
                    opacity=0.45,
                )
            )
    return group(shell + "".join(veins), f"translate({x} {y}) rotate({angle})")


def ginkgo(x, y, angle, size):
    rim = []
    for i in range(55):
        t = i / 54
        a = math.radians(201 + t * 137)
        r = size * (1 + 0.035 * math.sin(i * 1.27) - 0.13 * math.exp(-(((t - 0.5) * 15) ** 2)))
        rim.append((math.cos(a) * r, math.sin(a) * r))
    veins = "".join(
        path(f"M0 0Q{dx * 0.25:.1f} {dy * 0.49:.1f} {dx:.1f} {dy:.1f}", INK, 0.62, opacity=0.7)
        for dx, dy in rim[::2]
    )
    arc = "M0 0Q" + f"{rim[0][0] * 0.5:.0f} {rim[0][1] * 0.18:.0f} " + pts(rim)
    return group(
        path(arc + "Q12 -22 0 0Z", INK, 1.4, "url(#leaf)") + veins,
        f"translate({x} {y}) rotate({angle})",
    )


def fern(x, y, angle, scale=1):
    fronds = [path("M0 22C-2 -69 27 -148 12 -252", INK, 1.5)]
    for i in range(9):
        at = -12 - i * 24
        reach = round(88 * (1 - i / 10) + 5)
        for side in (-1, 1):
            fronds.append(
                leaf(i * 2, at, side * (62 - i * 3), reach, 8 + (9 - i) // 3, divisions=6)
            )
    return group("".join(fronds), f"translate({x} {y}) rotate({angle}) scale({scale})")


def rock_rings(x, y, size, angle=0, limit=19):
    forms = []
    for i in range(limit, 0, -1):
        r = size * i / limit
        edge = []
        for j in range(40):
            t = j * math.tau / 40
            rr = r * (1 + 0.065 * math.sin(3 * t + i / 6) + 0.04 * math.cos(5 * t - i / 9))
            edge.append((rr * math.cos(t) + i / 3, 0.81 * rr * math.sin(t) + i / 2))
        forms.append(
            path(
                "M" + pts(edge) + "Z",
                GOLD if i % 4 == 0 else INK,
                0.85,
                "url(#wood)" if i == limit else "none",
                0.9,
            )
        )
    forms.append(
        path(
            f"M0 0L-{size * 0.49:.0f} -{size * 0.58:.0f}m12 15-16 2M3 2L{size * 0.63:.0f} {size * 0.38:.0f}",
            INK,
            1.8,
            opacity=0.68,
        )
    )
    return group("".join(forms), f"translate({x} {y}) rotate({angle})")


def pine(x, y, height, shade):
    w = height * 0.19
    outline = [
        (0, -height),
        (-w * 0.38, -height * 0.59),
        (-w * 0.15, -height * 0.62),
        (-w * 0.71, -height * 0.33),
        (-w * 0.32, -height * 0.37),
        (-w, -height * 0.08),
        (-2, -height * 0.14),
        (-2, 0),
        (2, 0),
        (2, -height * 0.15),
        (w * 0.92, -height * 0.07),
        (w * 0.31, -height * 0.41),
        (w * 0.57, -height * 0.36),
        (w * 0.19, -height * 0.61),
        (w * 0.31, -height * 0.57),
    ]
    strokes = [path("M" + pts(outline) + "Z", shade, 0.55, shade)]
    for n in range(1, 6):
        t = n / 6
        strokes.append(
            path(
                f"M0 {-height * t:.1f}l{w * (1 - t) * 0.65:.1f} {height * 0.1:.1f}",
                FOLIO,
                0.5,
                opacity=0.4,
            )
        )
    return group("".join(strokes), f"translate({x} {y})")


def alpine(seed, dark=False):
    rng = random.Random(seed)
    furthest = "M-20 315L82 234 131 216 183 145 228 176 309 71 352 125 398 155 461 128 520 177 566 164 668 243V461H-20Z"
    nearby = "M-10 355Q56 266 144 311T298 328Q344 286 399 298T516 261Q575 228 657 257V460H-10Z"
    art = [
        ellipse(470, 102, 64, 64, GOLD, "#dce06c", 0.56),
        path(furthest, INK, 1.5, "#a7af8b"),
        path(nearby, INK, 1.35, "#778665"),
        path("M-10 388Q106 333 229 359T468 346Q561 324 661 344V460H-10Z", INK, 1, "#4b694c"),
    ]
    for sx, sy, end in ((183, 145, 242), (309, 71, 391), (461, 128, 545), (566, 164, 619)):
        art.append(
            path(
                f"M{sx} {sy}l14 40 -10 19 29 24 -14 17 37 46L{end} 307L{sx + 9} {sy + 35}Z",
                INK,
                0.85,
                "url(#hachure)",
                0.84,
            )
        )
        for i in range(10):
            yy = sy + 25 + i * 10
            xx = sx - i * 4
            art.append(line(xx, yy, xx + rng.randint(8, 39), yy - rng.randint(2, 13), INK, 0.29))
    for _ in range(48):
        x = rng.randrange(-12, 651)
        y = rng.randrange(322, 455)
        ht = rng.randrange(21, 111) if x < 180 or x > 462 else rng.randrange(16, 52)
        art.append(pine(x, y, ht, rng.choice(["#244833", "#1a392a", "#496b4b", "#5a744a"])))
    art.append(
        path(
            "M238 443Q320 391 401 372T590 339Q540 366 436 383T315 443Z",
            "#b6c294",
            0.7,
            "#dedbc1",
            0.7,
        )
    )
    return "".join(art) if not dark else '<g opacity=".56">' + "".join(art) + "</g>"


def sentinel_pine():
    """The landscape's near-field woodcut, layered over the distant ridges."""
    art = [
        path(
            "M216 440Q238 340 239 252Q250 168 250 63Q258 164 256 248Q249 344 247 440Z",
            INK,
            1.4,
            "#244833",
        )
    ]
    rng = random.Random(734)
    for y in range(96, 325, 25):
        spread = 16 + (y - 72) * 0.37
        for side in (-1, 1):
            tip = 249 + spread * side
            tail = y + rng.randrange(10, 29)
            art.append(
                path(
                    f"M248 {y}Q{249 + side * spread * 0.53:.0f} {y + 5} {tip:.0f} {tail}Q{249 + side * spread * 0.53:.0f} {tail + 3} 245 {y + 13}Z",
                    INK,
                    0.8,
                    "#315639",
                )
            )
            for i in range(12):
                t = (i + 1) / 13
                x = 249 + (tip - 249) * t
                at = y + (tail - y) * t
                art.append(
                    line(
                        x,
                        at,
                        x + side * rng.randrange(4, 17),
                        at + rng.randrange(4, 16),
                        "#244332",
                        0.83,
                    )
                )
                art.append(
                    line(
                        x,
                        at,
                        x + side * rng.randrange(3, 12),
                        at - rng.randrange(3, 12),
                        "#778750",
                        0.64,
                    )
                )
    for i in range(10):
        x = 218 + i * 2.7
        art.append(
            path(f"M{x:.0f} 443Q{x + 16:.0f} 347 {x + 19:.0f} 288", "#a0ac75", 0.6, opacity=0.43)
        )
    return "".join(art)


def flowering(cx, cy, r, petals):
    art = [
        ellipse(cx, cy, r + 19, r + 19, GOLD, opacity=0.49),
        ellipse(cx, cy, r + 31, r + 31, GOLD, opacity=0.31),
    ]
    for i in range(petals):
        art.append(leaf(cx, cy, i * 360 / petals, r, r * 0.18, divisions=9))
    art.extend(
        [ellipse(cx, cy, 32, 32, INK, "url(#wood)"), ellipse(cx, cy, 22, 22, GOLD, "url(#hachure)")]
    )
    for i in range(0, 360, 15):
        a = math.radians(i)
        art.append(
            line(
                cx + math.cos(a) * (r + 24),
                cy + math.sin(a) * (r + 24),
                cx + math.cos(a) * (r + 35),
                cy + math.sin(a) * (r + 35),
                GOLD,
            )
        )
    return "".join(art)


def contour(seed, count, start=63):
    rng = random.Random(seed)
    art = []
    for i in range(count):
        y = start + i * 19
        depth = rng.randrange(10, 30)
        d = f"M-14 {y}Q87 {y - depth} 161 {y + 17}T355 {y + 23}T654 {y - 15}"
        if i % 3 == 0:
            art.append(
                path(
                    d + f"L653 {y + 2}Q493 {y + 52} 348 {y + 39}T158 {y + 35}T-14 {y + 13}Z",
                    GOLD,
                    0.7,
                    "url(#hachure)",
                    0.72,
                )
            )
        art.append(path(d, INK, 1.1 if i % 3 == 0 else 0.65, opacity=0.7))
    return "".join(art)


def branch(x, y, angle, length, depth, rng):
    a = math.radians(angle)
    x2, y2 = x + math.cos(a) * length, y + math.sin(a) * length
    wobble = rng.randrange(-13, 14)
    art = path(
        f"M{x:.0f} {y:.0f}Q{(x + x2) / 2 + wobble:.0f} {(y + y2) / 2:.0f} {x2:.0f} {y2:.0f}",
        INK,
        0.75 + depth * 0.9,
    )
    if depth:
        for delta in (-29, 7, 36):
            art += branch(
                x2,
                y2,
                angle + delta + rng.randrange(-6, 7),
                length * rng.uniform(0.57, 0.72),
                depth - 1,
                rng,
            )
    else:
        art += ellipse(round(x2), round(y2), 2.6, 2.6, GOLD, LIME, 0.72)
    return art


def pod(x, y, angle, scale=1):
    art = path(
        "M0 72C-30 60-48 27-42-4S-13-40 0-48C17-33 40-31 45-6S28 59 0 72Z", INK, 1.5, "url(#wood)"
    )
    art += path("M-46-3Q-42-41 0-47Q39-43 47-5Q1 18-46-3Z", INK, 1.2, "url(#hachure)")
    art += path("M0-47q-8-17 3-31M0 72q2 7-2 12", INK, 1.5)
    for i in range(-24, 26, 6):
        art += path(f"M{i} 15Q{i * 1.45:.0f} 34 {i * 0.2:.0f} 62", GOLD, 0.6, opacity=0.69)
    return group(art, f"translate({x} {y}) rotate({angle}) scale({scale})")


def fossil(x, y):
    spiral = []
    spokes = []
    for i in range(172):
        t = i * 0.107
        r = 5 + i * 0.75
        tx, ty = x + r * math.cos(t), y + r * math.sin(t) * 0.78
        spiral.append((tx, ty))
        if i % 3 == 0 and i > 29:
            spokes.append(
                line(
                    tx,
                    ty,
                    x + (r - 19) * math.cos(t + 0.16),
                    y + (r - 19) * math.sin(t + 0.16) * 0.78,
                    GOLD,
                    0.8,
                )
            )
    return (
        ellipse(x, y, 164, 137, GOLD, "url(#wood)", 0.61)
        + path("M" + pts(spiral), INK, 2.4)
        + "".join(spokes)
    )


def calibrators(x, y, width, height):
    art = path(f"M{x} {y}h{width}v{height}h-{width}Z", GOLD, 0.75, opacity=0.58)
    for i in range(10, width, 10):
        art += line(x + i, y, x + i, y + (10 if i % 50 == 0 else 5), GOLD, 0.57)
    for i in range(10, height, 10):
        art += line(x, y + i, x + (10 if i % 50 == 0 else 5), y + i, GOLD, 0.57)
    return art


def shard():
    body = "M189 269L247 129 362 94 468 149 493 264 414 338 294 354Z"
    return (
        ellipse(341, 342, 160, 18, GOLD, "#d9c293", 0.48)
        + path(body, INK, 1.7, "url(#wood)")
        + path(
            "M247 129L317 193 362 94 393 219 468 149M189 269L317 193 302 275 294 354M317 193L393 219 302 275 414 338 393 219 493 264",
            INK,
            1.1,
        )
        + path(
            "M247 129L362 94 317 193Z M393 219L468 149 493 264Z M302 275L414 338 294 354Z",
            INK,
            0.4,
            "url(#hachure)",
            0.72,
        )
        + path("M317 193l-17 34 23 5-21 43 25-8 18 25-5 53", "#9b5b36", 2)
    )


def design():
    """Each entry defines an independent composition and its actual mount."""
    return [
        (
            "overview-ginkgo",
            "overview",
            "hero",
            "Ginkgo archival specimen",
            path(
                "M132 402Q256 336 389 137M211 359Q289 307 263 222M287 301Q388 268 473 277", INK, 3.1
            )
            + ginkgo(389, 137, 21, 116)
            + ginkgo(263, 222, -37, 107)
            + ginkgo(473, 277, 60, 95)
            + ginkgo(304, 318, -57, 68),
        ),
        (
            "overview-forest-engraving",
            "overview",
            "landscape",
            "Alpine forest engraving",
            alpine(19) + sentinel_pine(),
        ),
        (
            "datasets-herbarium",
            "datasets",
            "hero",
            "Four collected herbarium leaves",
            calibrators(95, 55, 445, 329)
            + leaf(194, 299, -16, 178, 45)
            + leaf(317, 302, 19, 199, 39, fill="url(#wood)")
            + leaf(467, 280, -11, 156, 55)
            + ginkgo(514, 347, 31, 73),
        ),
        (
            "contracts-pressed-fern",
            "contracts",
            "hero",
            "Pressed fern and archival folio",
            group(calibrators(40, 40, 358, 330), "translate(70 -2) rotate(-7 220 220)")
            + fern(332, 386, 14, 1.28)
            + path("M457 119h66m-66 18h44m-44 19h54M452 303q52 14 85-14", GOLD, 1.2),
        ),
        (
            "impact-specimen-pair",
            "impact",
            "hero",
            "Matched leaf specimens with a comparison rule",
            calibrators(50, 53, 254, 330)
            + calibrators(332, 53, 254, 330)
            + leaf(191, 347, -17, 217, 58)
            + leaf(445, 343, 17, 217, 58, fill="url(#wood)")
            + path("M275 230H360m-7-6 7 6-7 6", GOLD, 1.3),
        ),
        (
            "checks-calibration-rosette",
            "checks",
            "hero",
            "Rosette and calibration ring",
            flowering(336, 225, 126, 11),
        ),
        (
            "batches-sediment-register",
            "batches",
            "hero",
            "Sediment layers and indexed levels",
            contour(71, 18, 29)
            + calibrators(50, 33, 532, 358)
            + path("M122 341V75m-6 9 6-9 6 9M504 75V342m-6-9 6 9 6-9", GOLD, 1.5),
        ),
        (
            "quarantine-sealed-pod",
            "quarantine",
            "hero",
            "Seed isolated inside a sealed specimen outline",
            path(
                "M251 92H407L417 132V331Q417 350 398 350H249Q229 350 229 332V133Z",
                INK,
                1.55,
                "url(#glass)",
            )
            + path("M245 93v-23h169v23M245 312h154", GOLD, 1.3)
            + pod(319, 217, 14, 1.14)
            + calibrators(207, 62, 233, 307),
        ),
        (
            "versions-double-imprint",
            "versions",
            "hero",
            "Two cross sections from retained versions",
            rock_rings(202, 216, 117, -17, 15)
            + rock_rings(463, 224, 131, 19, 17)
            + path("M295 222h62m-54-8-8 8 8 8m46-16 8 8-8 8", GOLD, 1.25),
        ),
        (
            "lineage-root-etching",
            "lineage",
            "hero",
            "A trunk, crown and distinct root branches",
            branch(323, 229, -90, 80, 3, random.Random(21))
            + branch(323, 228, 88, 62, 3, random.Random(22))
            + path("M70 241Q326 211 589 247", GOLD, 0.95)
            + ellipse(324, 219, 194, 176, GOLD, opacity=0.39),
        ),
        (
            "incidents-fracture-plate",
            "incidents",
            "hero",
            "Geological fracture study",
            calibrators(100, 64, 443, 313)
            + shard()
            + path("M487 168L554 106M327 274L123 315", GOLD, 0.8),
        ),
        (
            "recovery-growth-rings",
            "recovery",
            "hero",
            "Tree growth rings with a retained reference",
            rock_rings(347, 211, 167, -9, 23)
            + path("M355 58Q506 77 532 206M526 195l6 11 6-10M200 275Q175 190 210 122", GOLD, 1.8)
            + ellipse(347, 211, 9, 9, GOLD, LIME, 0.63),
        ),
        (
            "agent-leaf-prism",
            "agent",
            "hero",
            "Prism breaking light across a leaf plate",
            leaf(366, 355, -17, 252, 63, fill="url(#glass)", divisions=23)
            + path(
                "M124 249L253 117 344 266 214 310ZM124 249l220 17m-91-149-39 193",
                INK,
                1.2,
                "url(#glass)",
                0.71,
            )
            + path(
                "M49 194L208 217 447 190 579 134M209 219L454 225 593 205M211 222L461 261 597 284",
                GOLD,
                1.2,
                opacity=0.8,
            ),
        ),
        (
            "connections-root-junction",
            "connections",
            "hero",
            "Four convergent root systems",
            branch(321, 218, -133, 76, 3, random.Random(95))
            + branch(321, 218, -47, 79, 3, random.Random(96))
            + branch(321, 218, 45, 81, 3, random.Random(97))
            + branch(321, 218, 132, 75, 3, random.Random(98))
            + ellipse(321, 218, 23, 23, GOLD, "url(#leaf)"),
        ),
        (
            "settings-alignment-folio",
            "settings",
            "hero",
            "Ruled specimen alignment folio",
            calibrators(98, 71, 448, 310)
            + path("M103 165h437M103 257h437M238 75v303M400 75v303", GOLD, 0.65, opacity=0.56)
            + leaf(183, 326, 13, 181, 35)
            + ginkgo(324, 243, -12, 90)
            + fern(461, 348, 1, 0.84),
        ),
        (
            "ledger-canopy-print",
            "overview",
            ".audit-ledger",
            "Canopy ink silhouette",
            alpine(33, True)
            + path(
                "M99 417Q164 211 268 89Q239 159 229 192Q344 129 489 106Q377 155 324 200Q433 185 531 204Q347 246 249 295L205 417Z",
                "#bbd183",
                2.4,
                "none",
                0.83,
            ),
        ),
        (
            "provenance-ammonite",
            "overview",
            ".evidence-rail",
            "Ammonite preserved in a provenance plate",
            fossil(388, 212),
        ),
        (
            "checks-acorn-collection",
            "checks",
            ".quality-benchmark",
            "Apache benchmark acorn specimen study",
            pod(379, 183, 24, 1.44)
            + pod(476, 230, -29, 1.18)
            + pod(322, 286, 51, 0.91)
            + leaf(419, 225, 63, 160, 29),
        ),
        (
            "impact-mineral-core",
            "impact",
            ".impact-source",
            "Longitudinal mineral core engraving",
            contour(22, 11, 116)
            + path("M136 113h411v208H136Q80 212 136 113Z", INK, 1.8)
            + ellipse(139, 216, 52, 103, GOLD, "url(#wood)")
            + ellipse(139, 216, 34, 78, INK),
        ),
        (
            "lineage-delta-channel",
            "lineage",
            ".lineage-flow",
            "Branching delta channels",
            contour(88, 14, 46) + branch(625, 234, 179, 177, 3, random.Random(30)),
        ),
        (
            "recovery-new-sprout",
            "recovery",
            ".recovery-steps",
            "Sprout returning from a retained seed",
            pod(359, 316, -15, 0.8)
            + path("M363 286Q370 234 329 166Q316 140 330 106", INK, 3.2)
            + leaf(351, 220, 69, 134, 38)
            + leaf(328, 162, -48, 109, 27, fill="url(#wood)"),
        ),
        (
            "agent-evidence-veins",
            "agent",
            ".grounding-panel",
            "Visible skeletal leaf veins",
            leaf(357, 403, -27, 315, 89, fill="url(#glass)", divisions=31)
            + leaf(391, 358, 36, 203, 47, fill="none", divisions=22),
        ),
    ]


def plate(drawing, index):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="440" viewBox="0 0 640 440">
<defs>
  <linearGradient id="paper" x2="1" y2="1"><stop stop-color="#faf3e3"/><stop offset="1" stop-color="#e4d6ad"/></linearGradient>
  <linearGradient id="leaf" x2=".8" y2="1"><stop stop-color="#e2e883"/><stop offset=".5" stop-color="#b7c54c"/><stop offset="1" stop-color="#688445"/></linearGradient>
  <radialGradient id="wood"><stop stop-color="#f2e2a9"/><stop offset="1" stop-color="#ad8754"/></radialGradient>
  <linearGradient id="glass" x2="1" y2="1"><stop stop-color="#fff9e8" stop-opacity=".58"/><stop offset="1" stop-color="#b9c77b" stop-opacity=".44"/></linearGradient>
  <pattern id="fibres" width="43" height="37" patternUnits="userSpaceOnUse"><path d="M2 3l4 1M31 12l5-1M16 21l1 3M38 30l3-2M5 34l3 1" stroke="#8b713f" stroke-opacity=".24" stroke-width=".5"/><circle cx="21" cy="7" r=".65" fill="#8b713f" opacity=".17"/></pattern>
  <pattern id="hachure" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-24)"><path d="M0 0v5" stroke="#415643" stroke-opacity=".45" stroke-width=".8"/></pattern>
</defs>
<rect width="640" height="440" fill="url(#paper)"/><rect width="640" height="440" fill="url(#fibres)"/>
<g fill="none" stroke="#8c784a" stroke-width=".7" opacity=".62"><path d="M30 52V31H51M589 31h21v21M610 389v21h-21M51 410H30v-21"/><path d="M18 31h24M30 19v24M598 410h24M610 398v24"/><circle cx="30" cy="31" r="7"/><circle cx="610" cy="410" r="7"/></g>
<g fill="none" stroke="{INK}">{drawing}</g>
<text x="577" y="52" fill="#5c573d" font-family="monospace" font-size="10" letter-spacing="2">{index:02}</text>
</svg>"""


def main():
    ART.mkdir(exist_ok=True)
    manifest = []
    for index, (name, route, placement, subject, drawing) in enumerate(design(), 1):
        filename = name + ".svg"
        content = plate(drawing, index)
        (ART / filename).write_text(content, encoding="utf-8")
        manifest.append(
            {
                "file": filename,
                "route": route,
                "placement": placement,
                "subject": subject,
                "source": "Original DataGuard artwork drawn in scripts/create_field_journal_art.py",
                "usage": "Original artwork created for the DataGuard repository",
                "format": "Standalone SVG, 640 by 440 viewBox, self-hosted, no external resources",
                "loading": "critical" if placement == "hero" else "lazy",
            }
        )
    (ROOT / "archive-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Created {len(manifest)} distinct field journal plates.")


if __name__ == "__main__":
    main()

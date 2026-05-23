/**
 * Vision Pipeline UI Audit Utility
 * Calculates element coordinates and detects unintended overlaps.
 */

window.auditLayout = function() {
    const elements = Array.from(document.querySelectorAll('body *:not(script):not(style)'))
        .filter(el => {
            const style = window.getComputedStyle(el);
            return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0;
        });

    const report = {
        timestamp: new Date().toISOString(),
        viewport: { width: window.innerWidth, height: window.innerHeight },
        overlaps: [],
        overflows: []
    };

    for (let i = 0; i < elements.length; i++) {
        const elA = elements[i];
        const rectA = elA.getBoundingClientRect();

        // Check for viewport overflow
        if (rectA.right > window.innerWidth || rectA.bottom > window.innerHeight || rectA.left < 0 || rectA.top < 0) {
            report.overflows.push({
                tag: elA.tagName,
                id: elA.id,
                classes: elA.className,
                rect: rectA
            });
        }

        for (let j = i + 1; j < elements.length; j++) {
            const elB = elements[j];
            const rectB = elB.getBoundingClientRect();

            // Intersection check
            const overlap = !(rectA.right < rectB.left || 
                             rectA.left > rectB.right || 
                             rectA.bottom < rectB.top || 
                             rectA.top > rectB.bottom);

            if (overlap) {
                // Ignore parent-child relationships as overlap is expected
                if (elA.contains(elB) || elB.contains(elA)) continue;

                // Ignore extremely small elements (deco)
                if (rectA.width < 5 || rectB.width < 5) continue;

                report.overlaps.push({
                    elementA: { tag: elA.tagName, id: elA.id, classes: elA.className.split(' ').slice(0,3).join('.') },
                    elementB: { tag: elB.tagName, id: elB.id, classes: elB.className.split(' ').slice(0,3).join('.') },
                    intersection: {
                        top: Math.max(rectA.top, rectB.top),
                        left: Math.max(rectA.left, rectB.left),
                        width: Math.min(rectA.right, rectB.right) - Math.max(rectA.left, rectB.left),
                        height: Math.min(rectA.bottom, rectB.bottom) - Math.max(rectA.top, rectB.top)
                    }
                });
            }
        }
    }

    console.group("🚀 Vision Pipeline Layout Audit");
    console.log("Total Elements Scanned:", elements.length);
    console.table(report.overlaps);
    console.groupEnd();

    // Visual feedback: Highlight overlaps
    report.overlaps.forEach(o => {
        const marker = document.createElement('div');
        marker.style.position = 'fixed';
        marker.style.zIndex = '9999';
        marker.style.border = '2px solid #ff00ff';
        marker.style.backgroundColor = 'rgba(255, 0, 255, 0.1)';
        marker.style.pointerEvents = 'none';
        marker.style.top = o.intersection.top + 'px';
        marker.style.left = o.intersection.left + 'px';
        marker.style.width = o.intersection.width + 'px';
        marker.style.height = o.intersection.height + 'px';
        document.body.appendChild(marker);
        setTimeout(() => marker.remove(), 5000);
    });

    return report;
};

import re

with open('web/frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ─────────────────────────────────────────────
# 1. CSS: flex-wrap wrap → nowrap
# ─────────────────────────────────────────────
content = content.replace(
    '            flex-wrap: wrap;\r\n            width: 100%;\r\n            box-sizing: border-box;\r\n        }',
    '            flex-wrap: nowrap;\r\n            width: 100%;\r\n            box-sizing: border-box;\r\n        }'
)
print("1. flex-wrap 변경 완료")

# ─────────────────────────────────────────────
# 2. HTML: shape-select-menu에서 🗑️ 제거, shape-delete-bar 추가
# ─────────────────────────────────────────────
old_shape_menu = (
    '                <!-- 두 번째 행: 도형 서브메뉴 (📐 누르면 아래에 나타남) -->\r\n'
    '                <div class="shape-select-menu" id="shape-select-menu">\r\n'
    '                    <button class="size-btn" onclick="addShape(\'line\')" title="직선" style="font-size: 16px; font-weight: bold;">➖</button>\r\n'
    '                    <button class="size-btn" onclick="addShape(\'triangle\')" title="삼각형" style="font-size: 16px;">▲</button>\r\n'
    '                    <button class="size-btn" onclick="addShape(\'rect\')" title="사각형" style="font-size: 16px;">■</button>\r\n'
    '                    <button class="size-btn" onclick="addShape(\'circle\')" title="원" style="font-size: 16px;">●</button>\r\n'
    '                    <div style="width: 1px; height: 20px; background-color: var(--border-color); margin: 0 2px;"></div>\r\n'
    '                    <button class="size-btn" onclick="deleteSelectedShape()" title="선택된 도형 삭제" style="font-size: 16px; color: var(--danger-color);">🗑️</button>\r\n'
    '                </div>'
)
new_shape_menu = (
    '                <!-- 두 번째 행: 도형 서브메뉴 (📐 누르면 아래에 나타남) -->\r\n'
    '                <div class="shape-select-menu" id="shape-select-menu">\r\n'
    '                    <button class="size-btn" onclick="addShape(\'line\')" title="직선" style="font-size: 16px; font-weight: bold;">➖</button>\r\n'
    '                    <button class="size-btn" onclick="addShape(\'triangle\')" title="삼각형" style="font-size: 16px;">▲</button>\r\n'
    '                    <button class="size-btn" onclick="addShape(\'rect\')" title="사각형" style="font-size: 16px;">■</button>\r\n'
    '                    <button class="size-btn" onclick="addShape(\'circle\')" title="원" style="font-size: 16px;">●</button>\r\n'
    '                </div>\r\n'
    '\r\n'
    '                <!-- 세 번째 행: 도형 선택 시 삭제 버튼 -->\r\n'
    '                <div id="shape-delete-bar" style="display: none; justify-content: center; align-items: center; gap: 6px; padding: 4px 8px; background: rgba(255, 77, 79, 0.08); border-radius: 10px; border: 1px solid rgba(255, 77, 79, 0.25);">\r\n'
    '                    <span style="font-size: 11px; color: var(--danger-color); font-weight: 600;">선택된 도형</span>\r\n'
    '                    <button class="size-btn" id="shape-delete-btn" onclick="deleteSelectedShape()" title="선택된 도형 삭제" style="font-size: 16px; color: var(--danger-color);">🗑️</button>\r\n'
    '                </div>'
)

if old_shape_menu in content:
    content = content.replace(old_shape_menu, new_shape_menu)
    print("2. HTML shape-select-menu 변경 완료")
else:
    print("2. WARNING: shape-select-menu 타겟을 찾지 못했습니다!")
    # 디버깅용 출력
    idx = content.find('shape-select-menu" id="shape-select-menu"')
    if idx >= 0:
        print(f"   근처 텍스트: {repr(content[idx:idx+300])}")

# ─────────────────────────────────────────────
# 3. JS: eraseAt 함수 교체 + shapeToContour + updateDeleteBar 삽입
# ─────────────────────────────────────────────
old_eraseAt = (
    '        function eraseAt(pos) {\r\n'
    '            const scale = Math.min(simCanvas.width / simData.width, simCanvas.height / simData.height);\r\n'
    '            const eraseRadius = currentEraseRadius / scale; // 동적 지우개 반경\r\n'
    '\r\n'
    '            // 1. 선(contour) 지우기\r\n'
    '            let newContours = [];\r\n'
    '            let erased = false;\r\n'
    '\r\n'
    '            for (let contour of activeContours) {\r\n'
    '                let currentChunk = [];\r\n'
    '                for (let pt of contour) {\r\n'
    '                    let d = Math.hypot(pt.x - pos.x, pt.y - pos.y);\r\n'
    '                    if (d > eraseRadius) {\r\n'
    '                        currentChunk.push(pt);\r\n'
    '                    } else {\r\n'
    '                        erased = true;\r\n'
    '                        if (currentChunk.length > 0) {\r\n'
    '                            newContours.push(currentChunk);\r\n'
    '                            currentChunk = [];\r\n'
    '                        }\r\n'
    '                    }\r\n'
    '                }\r\n'
    '                if (currentChunk.length > 0) {\r\n'
    '                    newContours.push(currentChunk);\r\n'
    '                }\r\n'
    '            }\r\n'
    '            if (erased) {\r\n'
    '                activeContours = newContours;\r\n'
    '            }\r\n'
    '\r\n'
    '            // 2. 도형(shape) 영역 지우기 - 지우개 원이 도형의 AABB(bounding box)와 겹치면 삭제\r\n'
    '            const prevShapeCount = shapes.length;\r\n'
    '            shapes = shapes.filter(s => {\r\n'
    '                // 도형의 bounding box (simData 좌표계)\r\n'
    '                const minX = Math.min(s.x, s.x + s.w) - eraseRadius;\r\n'
    '                const maxX = Math.max(s.x, s.x + s.w) + eraseRadius;\r\n'
    '                const minY = Math.min(s.y, s.y + s.h) - eraseRadius;\r\n'
    '                const maxY = Math.max(s.y, s.y + s.h) + eraseRadius;\r\n'
    '                const inBox = pos.x >= minX && pos.x <= maxX && pos.y >= minY && pos.y <= maxY;\r\n'
    '                if (inBox && selectedShape && selectedShape.id === s.id) {\r\n'
    '                    selectedShape = null; // 선택 해제\r\n'
    '                }\r\n'
    '                return !inBox; // 범위 내에 있으면 삭제\r\n'
    '            });\r\n'
    '\r\n'
    '            if (erased || shapes.length !== prevShapeCount) {\r\n'
    '                drawAll();\r\n'
    '            }\r\n'
    '        }'
)

new_eraseAt = (
    '        // 도형을 촘촘한 벡터 점으로 변환 (지우개 처리용)\r\n'
    '        function shapeToContour(s) {\r\n'
    '            const pts = [];\r\n'
    '            const SEG = 80;\r\n'
    '            if (s.type === \'rect\') {\r\n'
    '                const n = Math.ceil(SEG / 4);\r\n'
    '                for (let i = 0; i <= n; i++) pts.push({ x: s.x + s.w * i / n, y: s.y });\r\n'
    '                for (let i = 1; i <= n; i++) pts.push({ x: s.x + s.w, y: s.y + s.h * i / n });\r\n'
    '                for (let i = 1; i <= n; i++) pts.push({ x: s.x + s.w - s.w * i / n, y: s.y + s.h });\r\n'
    '                for (let i = 1; i <= n; i++) pts.push({ x: s.x, y: s.y + s.h - s.h * i / n });\r\n'
    '            } else if (s.type === \'circle\') {\r\n'
    '                const cx = s.x + s.w / 2, cy = s.y + s.h / 2;\r\n'
    '                const rx = Math.abs(s.w / 2), ry = Math.abs(s.h / 2);\r\n'
    '                for (let i = 0; i <= SEG; i++) {\r\n'
    '                    const rad = (i / SEG) * 2 * Math.PI;\r\n'
    '                    pts.push({ x: cx + rx * Math.cos(rad), y: cy + ry * Math.sin(rad) });\r\n'
    '                }\r\n'
    '            } else if (s.type === \'triangle\') {\r\n'
    '                const n = Math.ceil(SEG / 3);\r\n'
    '                const p1 = { x: s.x + s.w / 2, y: s.y };\r\n'
    '                const p2 = { x: s.x + s.w, y: s.y + s.h };\r\n'
    '                const p3 = { x: s.x, y: s.y + s.h };\r\n'
    '                for (let i = 0; i < n; i++) { const t = i / n; pts.push({ x: p1.x + (p2.x - p1.x) * t, y: p1.y + (p2.y - p1.y) * t }); }\r\n'
    '                for (let i = 0; i < n; i++) { const t = i / n; pts.push({ x: p2.x + (p3.x - p2.x) * t, y: p2.y + (p3.y - p2.y) * t }); }\r\n'
    '                for (let i = 0; i <= n; i++) { const t = i / n; pts.push({ x: p3.x + (p1.x - p3.x) * t, y: p3.y + (p1.y - p3.y) * t }); }\r\n'
    '            } else if (s.type === \'line\') {\r\n'
    '                for (let i = 0; i <= SEG; i++) {\r\n'
    '                    pts.push({ x: s.x + s.w * i / SEG, y: s.y + s.h * i / SEG });\r\n'
    '                }\r\n'
    '            }\r\n'
    '            return pts;\r\n'
    '        }\r\n'
    '\r\n'
    '        // 선택 도형 삭제 바 표시/숨김\r\n'
    '        function updateDeleteBar() {\r\n'
    '            const bar = document.getElementById(\'shape-delete-bar\');\r\n'
    '            if (!bar) return;\r\n'
    '            bar.style.display = selectedShape ? \'flex\' : \'none\';\r\n'
    '        }\r\n'
    '\r\n'
    '        function eraseAt(pos) {\r\n'
    '            const scale = Math.min(simCanvas.width / simData.width, simCanvas.height / simData.height);\r\n'
    '            const eraseRadius = currentEraseRadius / scale;\r\n'
    '\r\n'
    '            // 1. 선(contour) 지우기\r\n'
    '            let newContours = [];\r\n'
    '            let erased = false;\r\n'
    '\r\n'
    '            for (let contour of activeContours) {\r\n'
    '                let currentChunk = [];\r\n'
    '                for (let pt of contour) {\r\n'
    '                    let d = Math.hypot(pt.x - pos.x, pt.y - pos.y);\r\n'
    '                    if (d > eraseRadius) {\r\n'
    '                        currentChunk.push(pt);\r\n'
    '                    } else {\r\n'
    '                        erased = true;\r\n'
    '                        if (currentChunk.length > 0) {\r\n'
    '                            newContours.push(currentChunk);\r\n'
    '                            currentChunk = [];\r\n'
    '                        }\r\n'
    '                    }\r\n'
    '                }\r\n'
    '                if (currentChunk.length > 0) newContours.push(currentChunk);\r\n'
    '            }\r\n'
    '            if (erased) activeContours = newContours;\r\n'
    '\r\n'
    '            // 2. 도형(shape) 부분 지우기 - 지우개 원 범위와 겹치는 선분만 제거\r\n'
    '            const newShapes = [];\r\n'
    '            let shapeChanged = false;\r\n'
    '\r\n'
    '            for (const s of shapes) {\r\n'
    '                const bMinX = Math.min(s.x, s.x + s.w) - eraseRadius;\r\n'
    '                const bMaxX = Math.max(s.x, s.x + s.w) + eraseRadius;\r\n'
    '                const bMinY = Math.min(s.y, s.y + s.h) - eraseRadius;\r\n'
    '                const bMaxY = Math.max(s.y, s.y + s.h) + eraseRadius;\r\n'
    '                if (pos.x < bMinX || pos.x > bMaxX || pos.y < bMinY || pos.y > bMaxY) {\r\n'
    '                    newShapes.push(s);\r\n'
    '                    continue;\r\n'
    '                }\r\n'
    '                // 도형 → 촘촘한 점으로 변환 후 지우개 원 범위 내 점 제거\r\n'
    '                const pts = shapeToContour(s);\r\n'
    '                let chunk = [];\r\n'
    '                let anyRemoved = false;\r\n'
    '                for (const pt of pts) {\r\n'
    '                    const d = Math.hypot(pt.x - pos.x, pt.y - pos.y);\r\n'
    '                    if (d > eraseRadius) {\r\n'
    '                        chunk.push(pt);\r\n'
    '                    } else {\r\n'
    '                        anyRemoved = true;\r\n'
    '                        if (chunk.length > 1) activeContours.push(chunk);\r\n'
    '                        chunk = [];\r\n'
    '                    }\r\n'
    '                }\r\n'
    '                if (chunk.length > 1) activeContours.push(chunk);\r\n'
    '\r\n'
    '                if (anyRemoved) {\r\n'
    '                    shapeChanged = true;\r\n'
    '                    erased = true;\r\n'
    '                    if (selectedShape && selectedShape.id === s.id) {\r\n'
    '                        selectedShape = null;\r\n'
    '                        updateDeleteBar();\r\n'
    '                    }\r\n'
    '                } else {\r\n'
    '                    newShapes.push(s);\r\n'
    '                }\r\n'
    '            }\r\n'
    '            shapes = newShapes;\r\n'
    '            if (erased || shapeChanged) drawAll();\r\n'
    '        }'
)

if old_eraseAt in content:
    content = content.replace(old_eraseAt, new_eraseAt)
    print("3. eraseAt 함수 교체 완료")
else:
    print("3. WARNING: eraseAt 타겟을 찾지 못했습니다!")

# ─────────────────────────────────────────────
# 4. JS: deleteSelectedShape 에서 updateDeleteBar() 호출 추가
# ─────────────────────────────────────────────
old_delete = (
    '        function deleteSelectedShape() {\r\n'
    '            if (selectedShape) {\r\n'
    '                shapes = shapes.filter(s => s.id !== selectedShape.id);\r\n'
    '                selectedShape = null;\r\n'
    '                drawAll();\r\n'
    '            } else {\r\n'
    '                alert("삭제할 도형을 먼저 선택해 주세요.");\r\n'
    '            }\r\n'
    '        }'
)
new_delete = (
    '        function deleteSelectedShape() {\r\n'
    '            if (selectedShape) {\r\n'
    '                shapes = shapes.filter(s => s.id !== selectedShape.id);\r\n'
    '                selectedShape = null;\r\n'
    '                updateDeleteBar();\r\n'
    '                drawAll();\r\n'
    '            }\r\n'
    '        }'
)
if old_delete in content:
    content = content.replace(old_delete, new_delete)
    print("4. deleteSelectedShape 변경 완료")
else:
    print("4. WARNING: deleteSelectedShape 타겟을 찾지 못했습니다!")

# ─────────────────────────────────────────────
# 5. JS: startDrawingAt에서 도형 선택 후 updateDeleteBar() 호출
# ─────────────────────────────────────────────
old_hit = (
    '                    } else {\r\n'
    '                        selectedShape = null; // 허공 클릭 시 해제\r\n'
    '                    }\r\n'
    '                    drawAll();\r\n'
    '                    return;\r\n'
    '                }'
)
new_hit = (
    '                    } else {\r\n'
    '                        selectedShape = null; // 허공 클릭 시 해제\r\n'
    '                    }\r\n'
    '                    updateDeleteBar();\r\n'
    '                    drawAll();\r\n'
    '                    return;\r\n'
    '                }'
)
if old_hit in content:
    content = content.replace(old_hit, new_hit)
    print("5. startDrawingAt 클릭 후 updateDeleteBar 추가 완료")
else:
    print("5. WARNING: startDrawingAt 도형 선택 블록을 찾지 못했습니다!")

with open('web/frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ 패치 완료!")

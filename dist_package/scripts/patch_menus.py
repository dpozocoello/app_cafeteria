"""Patch: Actualiza la funcion loadMenus en admin_menus.html con imagen y QR."""
import re

with open('app/templates/admin_menus.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Nuevo bloque de loadMenus con imagen y QR
NEW_LOADMENUS = r"""// ─── MENÚS ──────────────────────────────────────────────────────────────────
let allProducts = [];
async function loadMenus() {
    const [menusRes, prodsRes] = await Promise.all([fetch('/api/menus/'), fetch('/api/products/')]);
    const menus = await menusRes.json();
    allProducts = await prodsRes.json();
    const container = document.getElementById('menus-list');
    if (!menus.length) {
        container.innerHTML = '<p style="color:var(--muted);text-align:center;padding:2rem">No hay menús creados.</p>';
        return;
    }
    container.innerHTML = menus.map(m => {
        const itemsTable = m.items.length ? `
            <table class="menu-items-table">
                <thead><tr><th>Foto</th><th>Producto</th><th>Categoría</th><th>Precio</th><th>Estado</th><th>Imagen</th></tr></thead>
                <tbody>${m.items.map(it => {
                    const thumb = it.image_url
                        ? `<img src="${it.image_url}" alt="${it.product_name}" onerror="this.parentNode.innerHTML='🍽️'">`
                        : '🍽️';
                    const avail = it.is_available
                        ? `<span class="avail-on" style="cursor:pointer" onclick="toggleAvail(${it.item_id})">✓ Disponible</span>`
                        : `<span class="avail-off" style="cursor:pointer" onclick="toggleAvail(${it.item_id})">✗ Agotado</span>`;
                    const delBtn = it.image_url
                        ? `<button class="btn btn-delete btn-sm" style="margin-left:.3rem" onclick="removeDishImage(${it.item_id})">✕</button>`
                        : '';
                    return `<tr>
                        <td><div class="dish-thumb">${thumb}</div></td>
                        <td>${it.product_name}</td>
                        <td style="color:var(--muted)">${it.category || '—'}</td>
                        <td style="color:var(--accent);font-weight:600">$${parseFloat(it.price).toFixed(2)}</td>
                        <td>${avail}</td>
                        <td>
                            <label class="upload-zone">
                                📷 ${it.image_url ? 'Cambiar' : 'Subir foto'}
                                <input type="file" accept="image/*" style="display:none" onchange="uploadDishImage(${it.item_id},this)">
                            </label>${delBtn}
                        </td>
                    </tr>`;
                }).join('')}</tbody>
            </table>` : '<div style="color:var(--muted);font-size:.82rem;margin-top:.4rem">Sin productos asignados</div>';

        return `
        <div class="card">
            <div class="menu-card" style="align-items:flex-start;gap:1rem">
                <div style="flex:1;min-width:0">
                    <div style="display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin-bottom:.4rem">
                        <strong style="font-size:1.05rem">${m.name}</strong>
                        <span style="font-size:.72rem;padding:.18rem .55rem;background:${m.is_active?'rgba(16,185,129,.15)':'rgba(255,255,255,.07)'};color:${m.is_active?'var(--success)':'var(--muted)'};border-radius:20px">${m.is_active ? 'Activo' : 'Inactivo'}</span>
                        <span style="font-size:.75rem;color:var(--muted)">${m.items.length} producto${m.items.length!==1?'s':''}</span>
                    </div>
                    <div style="font-size:.82rem;color:var(--muted);margin-bottom:.6rem">${m.description || ''}</div>
                    ${itemsTable}
                </div>
                <div style="display:flex;flex-direction:column;gap:.4rem;flex-shrink:0">
                    <button class="btn btn-edit btn-sm" onclick="editMenu(${m.id})">✏️ Editar</button>
                    <button class="btn btn-delete btn-sm" onclick="deleteMenu(${m.id})">🗑️ Eliminar</button>
                    <button class="btn btn-sm" style="background:rgba(16,185,129,.15);color:var(--success)" onclick="showMenuQR(${m.id},'${m.name.replace(/'/g,"\\'")}')">🔳 QR Menú</button>
                    <a href="/menu-digital/${m.id}" target="_blank" class="btn btn-sm" style="background:rgba(59,130,246,.15);color:var(--info);text-decoration:none">🌐 Ver Digital</a>
                </div>
            </div>
        </div>`;
    }).join('');
}
"""

# Reemplazar el bloque completo desde // ─── MENÚS hasta el cierre de loadMenus
pattern = r'// ─── MENÚS ─+\nlet allProducts = \[\];\nasync function loadMenus\(\) \{.*?\n\}\n'
match = re.search(pattern, content, re.DOTALL)
if match:
    content = content[:match.start()] + NEW_LOADMENUS + '\n' + content[match.end():]
    print(f'OK - reemplazado bloque en posición {match.start()}')
else:
    print('ERROR - patrón no encontrado')
    import sys; sys.exit(1)

with open('app/templates/admin_menus.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Archivo guardado')

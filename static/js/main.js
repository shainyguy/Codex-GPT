const revealEls = document.querySelectorAll('.reveal');
const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && e.target.classList.add('show')), { threshold: .12 });
revealEls.forEach(el => io.observe(el));

const guests = document.getElementById('guests');
const budget = document.getElementById('budget');
function calcBanquet(){ const o = document.getElementById('banquetResult'); if(!o||!guests||!budget) return; o.textContent = `Итого: ${(Number(guests.value)*Number(budget.value)).toLocaleString('ru-RU')} ₽`; }
if(guests&&budget){guests.oninput=calcBanquet;budget.oninput=calcBanquet;calcBanquet();}

async function getMenu(){ const r = await fetch('/api/menu'); return r.json(); }

(async () => {
  const dishDay = document.getElementById('dishDay');
  const comboList = document.getElementById('comboList');
  if (dishDay || comboList) {
    const menu = await getMenu();
    if(dishDay){
      dishDay.innerHTML = `<img src="${menu.dishOfDay.image}" alt="${menu.dishOfDay.name}"><div><h3>${menu.dishOfDay.name}</h3><p>${menu.dishOfDay.description}</p><p><s>${menu.dishOfDay.oldPrice} ₽</s> <b>${menu.dishOfDay.price} ₽</b></p></div>`;
    }
    if(comboList){ comboList.innerHTML = menu.comboSets.map(c=>`<article class="card"><h3>${c.name}</h3><p>${c.description}</p><b>${c.price} ₽</b></article>`).join(''); }
  }

  const menuContainer = document.getElementById('menuContainer');
  if(menuContainer){
    const menu = await getMenu();
    menuContainer.innerHTML = menu.categories.map(cat=>`<section class="menu-category reveal"><h2>${cat.title}</h2>${cat.slug==='bar'?'<p class="muted">Доставка алкоголя запрещена в РФ.</p>':''}<div class="menu-grid">${cat.items.map(item=>`<article class="menu-card" data-name="${item.name.toLowerCase()}" data-allergens="${(item.allergens||[]).join(',')}"><img src="${cat.image}" alt="${item.name}"><div><h3>${item.name}</h3><p>${item.weight} · ${item.prepTime} · ${item.calories} ккал</p><small>${(item.allergens||[]).length?(item.allergens||[]).join(', '):'Без аллергенов'}</small></div><div class="row"><strong>${item.price} ₽</strong><button class="btn add-to-cart" data-name="${item.name}" data-price="${item.price}" data-isbar="${item.isBar?'1':'0'}">В корзину</button></div></article>`).join('')}</div></section>`).join('');
    bindCart();
    bindFilters();
  }
})();

async function loadReviews(){
  const list = document.getElementById('reviewsList');
  if(!list) return;
  const data = await (await fetch('/api/reviews')).json();
  list.innerHTML = data.map(x=>`<article class="card"><b>${x.customer_name}</b><p>${'⭐'.repeat(x.rating)}</p><p>${x.text}</p></article>`).join('');
}
loadReviews();

const reviewForm = document.getElementById('reviewForm');
if(reviewForm){reviewForm.onsubmit = async e=>{e.preventDefault();const fd = new FormData(reviewForm);const res = await fetch('/api/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_name:fd.get('name'),rating:Number(fd.get('rating')),text:fd.get('text')})});const d=await res.json();alert(d.message||'OK');reviewForm.reset();};}

const contactForm = document.getElementById('contactForm');
if(contactForm){contactForm.onsubmit = async e=>{e.preventDefault();const fd = new FormData(contactForm);await fetch('/api/contact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:fd.get('name'),phone:fd.get('phone'),message:fd.get('message')})});alert('Заявка отправлена');contactForm.reset();};}

const cart = [];
function bindCart(){
  document.querySelectorAll('.add-to-cart').forEach(btn=>btn.onclick=()=>{
    const name=btn.dataset.name, price=Number(btn.dataset.price), isBar=btn.dataset.isbar==='1';
    const found=cart.find(x=>x.name===name); if(found) found.qty++; else cart.push({name,price,qty:1,isBar});
    renderCart();
  });
  const orderForm = document.getElementById('orderForm');
  if(orderForm){ orderForm.onsubmit = async e=>{e.preventDefault();if(!cart.length) return alert('Корзина пуста'); const fd = new FormData(orderForm); const payload=Object.fromEntries(fd.entries()); payload.items=cart; const r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); const d=await r.json(); if(!r.ok) return alert(d.error || 'Ошибка'); if(d.payment_url){location.href=d.payment_url;return;} alert(`Заказ #${d.order_id} принят`); cart.splice(0); renderCart(); orderForm.reset();}; }
}
function renderCart(){
  const items=document.getElementById('cartItems'), totalEl=document.getElementById('cartTotal'); if(!items||!totalEl) return;
  items.innerHTML = cart.map(i=>`<p>${i.name} × ${i.qty} — ${i.price*i.qty} ₽</p>`).join('');
  totalEl.textContent = `${cart.reduce((s,i)=>s+i.price*i.qty,0)} ₽`;
}

function bindFilters(){
  const search=document.getElementById('search'), allergen=document.getElementById('allergenFilter');
  const run=()=>{const q=(search?.value||'').toLowerCase(), a=(allergen?.value||'').toLowerCase(); document.querySelectorAll('.menu-card').forEach(c=>{const okQ=c.dataset.name.includes(q); const okA=!a || c.dataset.allergens.toLowerCase().includes(a); c.style.display=(okQ&&okA)?'':'none';});};
  if(search) search.oninput=run; if(allergen) allergen.onchange=run;
}

const loginForm = document.getElementById('loginForm');
if(loginForm){loginForm.onsubmit = async e=>{e.preventDefault();const fd = new FormData(loginForm);const r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:fd.get('username'),password:fd.get('password')})});if(r.ok){location.href='/admin';} else alert('Неверный логин/пароль');};}

(async()=>{
  const orders = document.getElementById('adminOrders');
  if(!orders) return;
  const res = await fetch('/api/admin');
  if(!res.ok){location.href='/admin'; return;}
  const data = await res.json();
  orders.innerHTML = data.orders.map(o=>`<div class="admin-item"><b>#${o.id} ${o.customer_name} · ${o.total} ₽</b><p>${o.phone} · ${o.address}</p><p>Статус: ${o.status}</p><select data-order="${o.id}"><option>new</option><option>confirmed</option><option>cooking</option><option>delivery</option><option>done</option><option>cancelled</option></select><button class="btn" data-save-order="${o.id}">Сменить статус</button><details><summary>Состав</summary><pre>${o.items_json}</pre></details></div>`).join('');
  document.querySelectorAll('[data-save-order]').forEach(btn=>btn.onclick=async()=>{const id=btn.dataset.saveOrder;const status=document.querySelector(`select[data-order='${id}']`).value;await fetch('/api/admin/order-status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,status})});alert('Статус обновлен');});

  const reviews = document.getElementById('adminReviews');
  reviews.innerHTML = data.reviews.map(r=>`<div class="admin-item"><b>${r.customer_name} (${r.rating}/5)</b><p>${r.text}</p><p>${r.approved? 'Опубликован':'На модерации'}</p><button class="btn" data-approve="${r.id}">Одобрить</button><button class="btn danger" data-delete="${r.id}">Удалить</button></div>`).join('');
  document.querySelectorAll('[data-approve]').forEach(btn=>btn.onclick=async()=>{await fetch('/api/admin/review-approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:btn.dataset.approve})});alert('Одобрено');location.reload();});
  document.querySelectorAll('[data-delete]').forEach(btn=>btn.onclick=async()=>{await fetch('/api/admin/review-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:btn.dataset.delete})});alert('Удалено');location.reload();});

  const contacts = document.getElementById('adminContacts');
  contacts.innerHTML = data.contacts.map(c=>`<div class="admin-item"><b>${c.name} · ${c.phone}</b><p>${c.message}</p></div>`).join('');
})();

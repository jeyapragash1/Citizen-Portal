let cart = JSON.parse(localStorage.getItem('cart')) || [];
let currentProducts = [];
let currentFilters = {};

// External images to use when a product does not provide an image or the image fails to load.
const EXTERNAL_PLACEHOLDER_IMAGES = [
    'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=1200&q=80&auto=format&fit=crop',
    'https://images.unsplash.com/photo-1513708928121-79c2b6f8d0b7?w=1200&q=80&auto=format&fit=crop',
    'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=1200&q=80&auto=format&fit=crop',
    'https://images.unsplash.com/photo-1503602642458-232111445657?w=1200&q=80&auto=format&fit=crop',
    'https://images.unsplash.com/photo-1515165562835-c3c0a14b5a63?w=1200&q=80&auto=format&fit=crop'
];

function hashCode(str) {
    if (!str) return 0;
    let h = 0;
    for (let i = 0; i < str.length; i++) {
        h = ((h << 5) - h) + str.charCodeAt(i);
        h |= 0; // Convert to 32bit integer
    }
    return Math.abs(h);
}

function getExternalImageById(id, idx) {
    const list = EXTERNAL_PLACEHOLDER_IMAGES;
    const key = hashCode(String(id || idx || ''));
    return list[key % list.length];
}

function setFallbackImage(imgEl, id, idx) {
    try {
        imgEl.src = getExternalImageById(id, idx);
    } catch (e) {
        // final fallback: 1x1 pixel
        imgEl.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
    }
}

// Initialize store
async function initStore() {
    await loadCategories();
    await loadProducts();
    updateCartCount();
}

// Load product categories
async function loadCategories() {
    const res = await fetch('/api/store/categories');
    const data = await res.json();
     
    const container = document.getElementById('category-filters');
    container.innerHTML = '';
     
    data.categories.forEach(category => {
        const label = document.createElement('label');
        label.innerHTML = `
            <input type="checkbox" name="category" value="${category}">
            ${category.charAt(0).toUpperCase() + category.slice(1)}
        `;
        container.appendChild(label);
    });
}

// Load products with filters
async function loadProducts() {
    const loading = document.getElementById('loading');
    loading.style.display = 'block';
     
    const params = new URLSearchParams();
     
    // Add filters 
    if (currentFilters.category) {
        params.append('category', currentFilters.category);
    }
    if (currentFilters.minPrice) {
        params.append('min_price', currentFilters.minPrice);
    }
    if (currentFilters.maxPrice) {
        params.append('max_price', currentFilters.maxPrice);
    }
    if (currentFilters.tags) {
        params.append('tags', currentFilters.tags.join(','));
    }
     
    // Add sorting
    const sortBy = document.getElementById('sort-by').value;
    params.append('sort', sortBy);
     
    try {
        const res = await fetch(`/api/store/products?${params}`);
        currentProducts = await res.json();
        displayProducts(currentProducts);
    } catch (error) {
        console.error('Error loading products:', error);
    } finally {
        loading.style.display = 'none';
    }
}

// Display products in grid
function displayProducts(products) {
    const container = document.getElementById('products-container');
     
    if (products.length === 0) {
        container.innerHTML = '<div class="no-products">No products found matching your criteria.</div>';
        return;
    }
     
    container.innerHTML = products.map(product => `
        <div class="product-card" onclick='openProductModal(${JSON.stringify(product.id)})'>
            <div class="product-image">
                 <img src="${(product.images && product.images[0] && String(product.images[0]).startsWith('http')) ? product.images[0] : getExternalImageById(product.id, 0)}"  
                     alt="${(product.name || '').replace(/"/g, '&quot;')}"  
                     onerror='this.onerror=null; setFallbackImage(this, ${JSON.stringify(product.id)}, 0)'>
                ${product.original_price ? `<div class="discount-badge">-${Math.round((1 - product.price/product.original_price) * 100)}%</div>` : ''}
            </div>
            <div class="product-info">
                <h3 class="product-name">${product.name}</h3>
                <div class="product-price">
                    ${product.original_price ?  
                        `<span class="original-price">LKR ${product.original_price.toLocaleString()}</span>` : ''}
                    <span class="current-price">LKR ${product.price.toLocaleString()}</span>
                </div>
                <div class="product-rating">
                    ${'★'.repeat(Math.floor(product.rating || 0))}${'☆'.repeat(5-Math.floor(product.rating || 0))}
                    <span class="rating-count">(${product.reviews_count || 0})</span>
                </div>
                <button class="add-to-cart-btn" onclick='addToCart(${JSON.stringify(product.id)}, event)'>
                    Add to Cart
                </button>
            </div>
        </div>
    `).join('');
}

// Cart management
function addToCart(productId, evt) {
    // If called from an onclick, stop propagation so the card click doesn't open the modal.
    try { if (evt && typeof evt.stopPropagation === 'function') evt.stopPropagation(); } catch (e) {}

    let product = currentProducts.find(p => String(p.id) === String(productId));
    if (!product) {
        // Fallback: try to infer product details from the DOM (useful if products not loaded yet)
        try {
            if (evt && evt.target) {
                const card = evt.target.closest('.product-card') || document.querySelector('.product-modal-content');
                if (card) {
                    const nameEl = card.querySelector('.product-name') || card.querySelector('h2');
                    const priceEl = card.querySelector('.current-price');
                    const imgEl = card.querySelector('img');
                    const inferredName = nameEl ? nameEl.textContent.trim() : `Product ${productId}`;
                    let inferredPrice = 0;
                    if (priceEl) {
                        inferredPrice = parseFloat(priceEl.textContent.replace(/[^0-9.-]+/g, '')) || 0;
                    }
                    product = { id: productId, name: inferredName, price: inferredPrice, images: [imgEl ? imgEl.src : getExternalImageById(productId,0)] };
                }
            }
        } catch (e) {
            console.warn('Could not infer product details from DOM', e);
        }
    }
    if (!product) return;
     
    const existingItem = cart.find(item => String(item.id) === String(productId));
    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({
            id: productId,
            name: product.name,
            price: product.price,
            // persist available stripe price id on the cart item so checkout can work even
            // when `currentProducts` is not populated (e.g., page reload)
            stripe_price_id: product.stripe_price_id || product.price_id || product.priceId || product.stripePriceId || null,
            image: (product.images && product.images[0]) ? product.images[0] : getExternalImageById(product.id, 0),
            quantity: 1
        });
    }
     
    updateCart();
    showNotification(`${product.name} added to cart!`);
}

function updateCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    updateCartModal();
}

function updateCartCount() {
    const count = cart.reduce((total, item) => total + item.quantity, 0);
    document.getElementById('cart-count').textContent = count;
}

function viewCart() {
    document.getElementById('cart-modal').style.display = 'block';
    updateCartModal();
}

function closeCart() {
    document.getElementById('cart-modal').style.display = 'none';
}

function updateCartModal() {
    const container = document.getElementById('cart-items');
    const total = document.getElementById('cart-total');
     
    if (cart.length === 0) {
        container.innerHTML = '<p>Your cart is empty</p>';
        total.textContent = '0';
        return;
    }
     
    container.innerHTML = cart.map(item => `
        <div class="cart-item">
            <img src="${(item.image && String(item.image).startsWith('http')) ? item.image : getExternalImageById(item.id,0)}" alt="${(item.name||'').replace(/"/g,'&quot;')}" onerror='this.onerror=null; setFallbackImage(this, ${JSON.stringify(item.id)}, 0)'>
            <div class="cart-item-info">
                <h4>${item.name}</h4>
                <div class="cart-item-price">LKR ${item.price.toLocaleString()}</div>
            </div>
            <div class="cart-item-controls">
                <button onclick='updateQuantity(${JSON.stringify(item.id)}, -1)'>-</button>
                <span>${item.quantity}</span>
                <button onclick='updateQuantity(${JSON.stringify(item.id)}, 1)'>+</button>
                <button onclick='removeFromCart(${JSON.stringify(item.id)})'>Remove</button>
            </div>
        </div>
    `).join('');
     
    const cartTotal = cart.reduce((total, item) => total + (item.price * item.quantity), 0);
    total.textContent = cartTotal.toLocaleString();
}

function updateQuantity(productId, change) {
    const item = cart.find(item => String(item.id) === String(productId));
    if (item) {
        item.quantity += change;
        if (item.quantity <= 0) {
            removeFromCart(productId);
        } else {
            updateCart();
        }
    }
}

function removeFromCart(productId) {
    cart = cart.filter(item => String(item.id) !== String(productId));
    updateCart();
}

// Product modal with enhanced view
async function openProductModal(productId) {
    const product = currentProducts.find(p => String(p.id) === String(productId));
    if (!product) return;
     
    const modal = document.getElementById('product-modal');
    const content = document.getElementById('modal-content');
     
    content.innerHTML = `
        <div class="product-modal-content">
            <div class="product-modal-images">
                <img src="${(product.images && product.images[0] && String(product.images[0]).startsWith('http')) ? product.images[0] : getExternalImageById(product.id, 0)}" alt="${(product.name||'').replace(/"/g, '&quot;')}" class="main-image" onerror='this.onerror=null; setFallbackImage(this, ${JSON.stringify(product.id)}, 0)'>
                <div class="image-thumbnails">
                    ${ (product.images && product.images.length ? product.images : [getExternalImageById(product.id,0)]).map(img =>  
                        `<img src="${img}" alt="Thumbnail" onclick="changeMainImage(this.src)" onerror='this.onerror=null; setFallbackImage(this, ${JSON.stringify(product.id)}, 0)'>`
                    ).join('')}
                </div>
            </div>
            <div class="product-modal-details">
                <h2>${product.name}</h2>
                <div class="product-price-large">
                    ${product.original_price ?  
                        `<span class="original-price">LKR ${product.original_price.toLocaleString()}</span>` : ''}
                    <span class="current-price">LKR ${product.price.toLocaleString()}</span>
                </div>
                <div class="product-rating-large">
                    ${'★'.repeat(Math.floor(product.rating))}${'☆'.repeat(5-Math.floor(product.rating))}
                    <span>${product.rating} (${product.reviews_count} reviews)</span>
                </div>
                <p class="product-description">${product.description}</p>
                 
                <div class="product-features">
                    <h4>Features:</h4>
                    <ul>
                        ${product.features.map(feature => `<li>${feature}</li>`).join('')}
                    </ul>
                </div>
                 
                <div class="delivery-options">
                    <h4>Delivery Options:</h4>
                    ${product.delivery_options.map(option =>  
                        `<span class="delivery-badge">${option}</span>`
                    ).join('')}
                </div>
                 
                <div class="product-actions">
                    <button class="buy-now-btn" onclick='buyNow(${JSON.stringify(product.id)}, event)'>Buy Now</button>
                    <button class="add-to-cart-large" onclick='addToCart(${JSON.stringify(product.id)}, event)'>Add to Cart</button>
                </div>
            </div>
        </div>
    `;
     
    modal.style.display = 'block';
}

function changeMainImage(src) {
    document.querySelector('.main-image').src = src;
}

// Buy Now: prefer Stripe Checkout (server) if product has a Stripe Price ID,
// otherwise fallback to a development quick-pay flow using existing order/payment endpoints.
async function buyNow(productId) {
    const product = currentProducts.find(p => p.id === productId || String(p.id) === String(productId));
    if (!product) return;

    const priceId = product.stripe_price_id || product.price_id || product.priceId || product.stripePriceId;
    if (priceId) {
        try {
            const res = await fetch('/api/store/create_checkout_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'same-origin',
                body: JSON.stringify({price_id: priceId, quantity: 1})
            });
            const data = await res.json();
            if (data && data.url) {
                // Redirect user to Stripe Checkout
                window.location.href = data.url;
                return;
            } else {
                console.error('No checkout URL returned', data);
                showNotification('Could not create checkout session.');
            }
        } catch (err) {
            console.error('Error creating checkout session', err);
            showNotification('Checkout failed. Please try again.');
        }
    }

    // Fallback dev flow: create an order and mark payment verified (development only)
    try {
        const orderData = {
            user_id: typeof profile_id !== 'undefined' ? profile_id : null,
            items: [{id: product.id, name: product.name, price: product.price, quantity: 1}],
            total_amount: product.price,
            payment_method: 'card'
        };

        const or = await fetch('/api/store/order', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(orderData)
        });
        const orj = await or.json();
        if (orj && orj.status === 'ok') {
            const pay = await fetch('/api/store/payment', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({order_id: orj.order_id, user_id: orderData.user_id, amount: product.price, method: 'card', items: orderData.items, verified: true})
            });
            const payj = await pay.json();
            if (payj && payj.status === 'ok') {
                showNotification('Purchase completed (dev mode). Thank you!');
                // Remove item from cart if present
                cart = cart.filter(i => String(i.id) !== String(product.id));
                updateCart();
                closeModal();
                return;
            }
        }
        showNotification('Purchase failed.');
    } catch (err) {
        console.error('Fallback purchase error', err);
        showNotification('Purchase failed.');
    }
}

function closeModal() {
    document.getElementById('product-modal').style.display = 'none';
}

// Filter functions
function toggleFilters() {
    const sidebar = document.getElementById('filters-sidebar');
    sidebar.style.display = sidebar.style.display === 'none' ? 'block' : 'none';
}

function applyFilters() {
const categoryCheckboxes = document.querySelectorAll('input[name="category"]:checked');
const deliveryCheckboxes = document.querySelectorAll('input[name="delivery"]:checked');
currentFilters = {
category: Array.from(categoryCheckboxes).map(cb => cb.value).join(','),
delivery: Array.from(deliveryCheckboxes).map(cb => cb.value),
minPrice: document.getElementById('min-price').textContent.replace(/,/g, ''),
maxPrice: document.getElementById('max-price').textContent.replace(/,/g, '')
};
loadProducts();
}
function clearFilters() {
document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
document.getElementById('price-range').value = 500000;
updatePriceDisplay();
currentFilters = {};
loadProducts();
}
// Price range display
function updatePriceDisplay() {
const range = document.getElementById('price-range');
    const minPrice = document.getElementById('min-price');
    const maxPrice = document.getElementById('max-price');
     
    minPrice.textContent = '0';
    maxPrice.textContent = parseInt(range.value).toLocaleString();
}
 
// Checkout process: attempt Stripe Checkout for the entire cart when possible,
// otherwise fall back to the existing order/payment dev flow.
async function checkout() {
    // If profile_id isn't available, show a lightweight in-store profile prompt
    if (typeof profile_id === 'undefined' || !profile_id) {
        const ok = await showStoreProfilePrompt();
        if (!ok) return; // user cancelled or profile not created
    }

    // Ensure we have the latest products loaded so we can resolve price ids from them.
    if (!currentProducts || currentProducts.length === 0) {
        try {
            await loadProducts();
        } catch (e) {
            console.debug('Could not load products before checkout', e);
        }
    }

    // Build Stripe line_items from cart if products have Stripe price ids
    const lineItems = [];
    let allHavePriceId = true;
    for (const item of cart) {
        const prod = currentProducts.find(p => String(p.id) === String(item.id));
        // Prefer a price id stored on the cart item (persisted at add time),
        // otherwise fall back to product object if available.
        const priceId = item.stripe_price_id || item.price_id || (prod && (prod.stripe_price_id || prod.price_id || prod.priceId || prod.stripePriceId));
        if (priceId) {
            lineItems.push({price: priceId, quantity: item.quantity});
        } else {
            allHavePriceId = false;
        }
    }

    if (lineItems.length > 0 && allHavePriceId) {
        // Try to create a Checkout session for the cart
        try {
            const res = await fetch('/api/store/create_checkout_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'same-origin',
                body: JSON.stringify({line_items: lineItems})
            });
            const data = await res.json();
            if (data && data.url) {
                window.location.href = data.url;
                return;
            } else {
                console.error('Stripe session not created', data);
                showNotification('Could not create checkout session. Proceeding with fallback.');
            }
        } catch (err) {
            console.error('Error creating checkout session', err);
            showNotification('Checkout failed. Proceeding with fallback.');
        }
    }
    // If some items have Stripe price IDs but not all, offer to pay for the eligible items now
    if (lineItems.length > 0 && !allHavePriceId) {
        const proceed = confirm(`Some items in your cart cannot be paid via Stripe. Pay for ${lineItems.length} item(s) now and keep the rest in your cart?`);
        if (proceed) {
            try {
                const res = await fetch('/api/store/create_checkout_session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'same-origin',
                    body: JSON.stringify({line_items: lineItems})
                });
                const data = await res.json();
                if (data && data.url) {
                    // Remove paid items from cart before redirecting
                    const paidPriceSet = new Set(lineItems.map(li => li.price));
                    cart = cart.filter(item => !(item.stripe_price_id && paidPriceSet.has(item.stripe_price_id)));
                    updateCart();
                    window.location.href = data.url;
                    return;
                } else {
                    console.error('Stripe session not created for partial cart', data);
                    showNotification('Could not create checkout session for eligible items. Proceeding with fallback.');
                }
            } catch (err) {
                console.error('Error creating partial checkout session', err);
                showNotification('Checkout failed. Proceeding with fallback.');
            }
        }
    }

    // Fallback flow: create order and process payment (development mode)
    const orderData = {
        user_id: profile_id,
        items: cart,
        total_amount: cart.reduce((total, item) => total + (item.price * item.quantity), 0),
        payment_method: 'card'
    };

    try {
        const res = await fetch('/api/store/order', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(orderData)
        });

        const result = await res.json();
        if (result.status === 'ok') {
            // Process payment (dev fallback will mark verified if requested)
            await processPayment(result.order_id);
        } else {
            showNotification('Could not create order.');
        }
    } catch (error) {
        console.error('Checkout error:', error);
        showNotification('Checkout failed. Please try again.');
    }
}
 
async function processPayment(orderId) {
    const paymentData = {
        order_id: orderId,
        user_id: profile_id,
        amount: cart.reduce((total, item) => total + (item.price * item.quantity), 0),
        method: 'card',
        items: cart
    };
     
    try {
        const res = await fetch('/api/store/payment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(paymentData)
        });
         
        const result = await res.json();
        if (result.status === 'ok') {
            showNotification('Payment successful! Thank you for your purchase.');
            cart = [];
            updateCart();
            closeCart();
        }
    } catch (error) {
        console.error('Payment error:', error);
        showNotification('Payment failed. Please try again.');
    }
}

// Show a simple profile prompt overlay when global profile is not available.
// Returns true when profile created/available; false if cancelled.
function ensureStoreProfileElements() {
    if (document.getElementById('store-profile-overlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'store-profile-overlay';
    overlay.innerHTML = `
        <div class="panel">
            <h3>Tell us about you</h3>
            <input id="sp_name" type="text" placeholder="Full name" required>
            <input id="sp_age" type="number" placeholder="Age" required>
            <input id="sp_email" type="email" placeholder="Email (optional)">
            <div class="actions">
                <button id="sp_cancel">Cancel</button>
                <button id="sp_submit" class="proceed-btn">Continue</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);
    document.getElementById('sp_cancel').addEventListener('click', () => { overlay.style.display = 'none'; });
}

async function showStoreProfilePrompt() {
    ensureStoreProfileElements();
    const overlay = document.getElementById('store-profile-overlay');
    overlay.style.display = 'flex';

    return await new Promise((resolve) => {
        const submitBtn = document.getElementById('sp_submit');
        const cancelBtn = document.getElementById('sp_cancel');

        async function onSubmit(e) {
            e && e.preventDefault();
            submitBtn.disabled = true;
            const name = document.getElementById('sp_name').value.trim();
            const age = document.getElementById('sp_age').value.trim();
            const email = document.getElementById('sp_email').value.trim();
            if (!name || !age) {
                alert('Name and age are required.');
                submitBtn.disabled = false;
                return;
            }

            try {
                const res = await fetch('/api/profile/step', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({step: 'all', data: {name, age, email, phone: '', job: '', desires: []}})
                });
                const j = await res.json();
                if (j && j.profile_id) {
                    window.profile_id = j.profile_id;
                    // Ensure server-side session is established for this profile (login) so protected endpoints allow checkout
                    try {
                        // Call dev login helper with profile_id to set session cookie
                        const loginRes = await fetch('/api/user/login', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({profile_id: j.profile_id})
                        });
                        const loginJson = await loginRes.json().catch(() => ({}));
                        if (loginJson && loginJson.status === 'ok') {
                            // Now attempt auto-checkout if cart items have Stripe price IDs
                            if (cart && cart.length > 0) {
                                // Ensure products are loaded so we can resolve price ids
                                if (!currentProducts || currentProducts.length === 0) {
                                    try { await loadProducts(); } catch (e) { console.debug('Could not load products for auto-checkout', e); }
                                }
                                const lineItems = [];
                                let allHavePriceId = true;
                                for (const item of cart) {
                                    const prod = currentProducts.find(p => String(p.id) === String(item.id));
                                    const priceId = item.stripe_price_id || item.price_id || (prod && (prod.stripe_price_id || prod.price_id || prod.priceId || prod.stripePriceId));
                                    if (priceId) {
                                        lineItems.push({price: priceId, quantity: item.quantity});
                                    } else {
                                        allHavePriceId = false;
                                    }
                                }
                                if (lineItems.length > 0 && allHavePriceId) {
                                    const sres = await fetch('/api/store/create_checkout_session', {
                                        method: 'POST', headers: {'Content-Type': 'application/json'},
                                        credentials: 'same-origin',
                                        body: JSON.stringify({line_items: lineItems})
                                    });
                                    const sdata = await sres.json().catch(() => ({}));
                                    if (sdata && sdata.url) {
                                        // Redirect to Stripe Checkout
                                        window.location.href = sdata.url;
                                        return; // navigation will occur
                                    } else {
                                        console.debug('Stripe session not returned or missing url:', sdata);
                                    }
                                }
                                // If some items eligible but not all, offer partial checkout
                                if (lineItems.length > 0 && !allHavePriceId) {
                                    const proceed = confirm(`Some items in your cart cannot be paid via Stripe. Pay for ${lineItems.length} item(s) now and keep the rest in your cart?`);
                                    if (proceed) {
                                        try {
                                            const sres2 = await fetch('/api/store/create_checkout_session', {
                                                method: 'POST', headers: {'Content-Type': 'application/json'},
                                                credentials: 'same-origin',
                                                body: JSON.stringify({line_items: lineItems})
                                            });
                                            const sdata2 = await sres2.json().catch(() => ({}));
                                            if (sdata2 && sdata2.url) {
                                                // Remove paid items from cart before redirecting
                                                const paidPriceSet = new Set(lineItems.map(li => li.price));
                                                cart = cart.filter(item => !(item.stripe_price_id && paidPriceSet.has(item.stripe_price_id)));
                                                updateCart();
                                                window.location.href = sdata2.url;
                                                return;
                                            }
                                        } catch (e) {
                                            console.debug('Partial auto-checkout failed', e);
                                        }
                                    }
                                }
                            }
                        } else {
                            console.debug('Auto-login failed after profile creation', loginJson);
                        }
                    } catch (err) {
                        console.error('Auto-login/auto-checkout after profile creation failed:', err);
                    }

                    // Close overlay and resolve so callers (like checkout()) can continue fallback flow
                    overlay.style.display = 'none';
                    submitBtn.removeEventListener('click', onSubmit);
                    cancelBtn.removeEventListener('click', onCancel);
                    resolve(true);
                    return;
                }
            } catch (err) {
                console.error('Failed to create profile:', err);
            }
            submitBtn.disabled = false;
            alert('Failed to create profile. Please try again.');
        }

        function onCancel() {
            overlay.style.display = 'none';
            submitBtn.removeEventListener('click', onSubmit);
            cancelBtn.removeEventListener('click', onCancel);
            resolve(false);
        }

        submitBtn.addEventListener('click', onSubmit);
        cancelBtn.addEventListener('click', onCancel);
    });
}

// Utility functions
function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;
    document.body.appendChild(notification);
     
    setTimeout(() => {
        notification.remove();
    }, 3000);
}
// Initialize when page loads
document.addEventListener('DOMContentLoaded', initStore);

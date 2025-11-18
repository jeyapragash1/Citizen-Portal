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
        <div class="product-card" onclick="openProductModal(${JSON.stringify(product.id)})">
            <div class="product-image">
                <img src="${product.images && product.images[0] ? product.images[0] : getExternalImageById(product.id, 0)}"  
                     alt="${(product.name || '').replace(/"/g, '&quot;')}"  
                     onerror="this.onerror=null; setFallbackImage(this, ${JSON.stringify(product.id)}, 0)">
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
                <button class="add-to-cart-btn" onclick="event.stopPropagation(); addToCart(${JSON.stringify(product.id)})">
                    Add to Cart
                </button>
            </div>
        </div>
    `).join('');
}

// Cart management
function addToCart(productId) {
    const product = currentProducts.find(p => p.id === productId);
    if (!product) return;
     
    const existingItem = cart.find(item => item.id === productId);
    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({
            id: productId,
            name: product.name,
            price: product.price,
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
            <img src="${item.image || getExternalImageById(item.id,0)}" alt="${(item.name||'').replace(/"/g,'&quot;')}" onerror="this.onerror=null; setFallbackImage(this, ${JSON.stringify(item.id)}, 0)">
            <div class="cart-item-info">
                <h4>${item.name}</h4>
                <div class="cart-item-price">LKR ${item.price.toLocaleString()}</div>
            </div>
            <div class="cart-item-controls">
                <button onclick="updateQuantity('${item.id}', -1)">-</button>
                <span>${item.quantity}</span>
                <button onclick="updateQuantity('${item.id}', 1)">+</button>
                <button onclick="removeFromCart('${item.id}')">Remove</button>
            </div>
        </div>
    `).join('');
     
    const cartTotal = cart.reduce((total, item) => total + (item.price * item.quantity), 0);
    total.textContent = cartTotal.toLocaleString();
}

function updateQuantity(productId, change) {
    const item = cart.find(item => item.id === productId);
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
    cart = cart.filter(item => item.id !== productId);
    updateCart();
}

// Product modal with enhanced view
async function openProductModal(productId) {
    const product = currentProducts.find(p => p.id === productId);
    if (!product) return;
     
    const modal = document.getElementById('product-modal');
    const content = document.getElementById('modal-content');
     
    content.innerHTML = `
        <div class="product-modal-content">
            <div class="product-modal-images">
                <img src="${product.images && product.images[0] ? product.images[0] : getExternalImageById(product.id, 0)}" alt="${(product.name||'').replace(/"/g, '&quot;')}" class="main-image" onerror="this.onerror=null; setFallbackImage(this, ${JSON.stringify(product.id)}, 0)">
                <div class="image-thumbnails">
                    ${ (product.images && product.images.length ? product.images : [getExternalImageById(product.id,0)]).map(img =>  
                        `<img src="${img}" alt="Thumbnail" onclick="changeMainImage(this.src)" onerror="this.onerror=null; setFallbackImage(this, ${JSON.stringify(product.id)}, 0)">`
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
                    <button class="buy-now-btn" onclick="buyNow('${product.id}')">Buy Now</button>
                    <button class="add-to-cart-large" onclick="addToCart('${product.id}')">Add to Cart</button>
                </div>
            </div>
        </div>
    `;
     
    modal.style.display = 'block';
}

function changeMainImage(src) {
    document.querySelector('.main-image').src = src;
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
 
// Checkout process
async function checkout() {
    if (!profile_id) {
        showProfileModal();
        return;
    }
     
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
            // Process payment 
            await processPayment(result.order_id);
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

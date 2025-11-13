let cart = JSON.parse(localStorage.getItem('cart')) || [];
let currentProducts = [];
let currentFilters = {};

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
        <div class="product-card" onclick="openProductModal('${product.id}')">
            <div class="product-image">
                <img src="${product.images[0] || '/static/store/placeholder.jpg'}"  
                     alt="${product.name}"  
                     onerror="this.src='/static/store/placeholder.jpg'">
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
                    ${'★'.repeat(Math.floor(product.rating))}${'☆'.repeat(5-Math.floor(product.rating))}
                    <span class="rating-count">(${product.reviews_count})</span>
                </div>
                <button class="add-to-cart-btn" onclick="event.stopPropagation(); addToCart('${product.id}')">
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
            image: product.images[0],
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
            <img src="${item.image}" alt="${item.name}">
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
                <img src="${product.images[0]}" alt="${product.name}" class="main-image">
                <div class="image-thumbnails">
                    ${product.images.map(img =>  
                        `<img src="${img}" alt="Thumbnail" onclick="changeMainImage(this.src)">`
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

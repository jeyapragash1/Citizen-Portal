// Floating Chatbot UI Logic (standalone)
document.addEventListener('DOMContentLoaded', function() {
    const floatingBtn = document.getElementById('floating-chatbot-btn');
    const chatbotModal = document.getElementById('chatbot-modal');
    const closeBtn = document.getElementById('close-chatbot-modal');
    const messagesDiv = document.getElementById('chatbot-messages');
    const input = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send-btn');

    // Open modal
    if (floatingBtn) {
        floatingBtn.addEventListener('click', function() {
            chatbotModal.style.display = 'flex';
            input.focus();
            if (messagesDiv.childElementCount === 0) {
                appendChatbotMessage('bot', "Hi! I'm your virtual assistant. How can I help you?", new Date());
            }
        });
    }
    // Close modal
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            chatbotModal.style.display = 'none';
            input.value = '';
        });
    }
    // Send message
    if (sendBtn) {
        sendBtn.addEventListener('click', sendChatbotMessage);
    }
    if (input) {
        input.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') sendChatbotMessage();
        });
    }

    async function sendChatbotMessage() {
        const text = input.value.trim();
        if (!text) return;
        appendChatbotMessage('user', text, new Date());
        input.value = '';
        try {
            const res = await fetch("/api/ai/search", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({query: text, top_k: 5})
            });
            const data = await res.json();
            let reply = data.answer || "I'm sorry, I couldn't find an answer to that. Please try rephrasing your question.";
            appendChatbotMessage('bot', reply, new Date());
        } catch (error) {
            appendChatbotMessage('bot', "Oops! Something went wrong with the AI assistant. Please try again later.", new Date());
        }
    }

    function appendChatbotMessage(sender, text, timestamp) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chatbot-message ${sender}`;
        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chatbot-avatar';
        if (sender === 'bot') {
            avatarDiv.innerHTML = '<i class="fas fa-robot"></i>';
        } else {
            avatarDiv.innerHTML = '<i class="fas fa-user"></i>';
        }
        // Bubble
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'chatbot-bubble';
        bubbleDiv.innerText = text;
        // Timestamp
        const tsDiv = document.createElement('div');
        tsDiv.className = 'chatbot-timestamp';
        tsDiv.innerText = formatTimestamp(timestamp);
        // Layout
        if (sender === 'bot') {
            msgDiv.appendChild(avatarDiv);
            msgDiv.appendChild(bubbleDiv);
        } else {
            msgDiv.appendChild(bubbleDiv);
            msgDiv.appendChild(avatarDiv);
        }
        msgDiv.appendChild(tsDiv);
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function formatTimestamp(date) {
        if (!date) return '';
        const d = new Date(date);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    }
});

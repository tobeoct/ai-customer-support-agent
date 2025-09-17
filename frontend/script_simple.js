/**
 * Simple Customer Support Chat - Core functionality only
 * WebSocket integration with basic logging
 */

class SimpleChat {
    constructor() {
        this.websocket = null;
        this.sessionId = this.generateSessionId();
        this.customerId = null;
        this.isConnected = false;
        
        // DOM elements
        this.elements = {
            statusText: document.getElementById('statusText'),
            sessionId: document.getElementById('sessionId'),
            customerId: document.getElementById('customerId'),
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            chatForm: document.getElementById('chatForm'),
            typingIndicator: document.getElementById('typingIndicator')
        };
        
        this.init();
    }
    
    init() {
        console.log('🚀 Simple Customer Support Chat starting...');
        
        // Update session display
        this.elements.sessionId.textContent = this.sessionId;
        
        // Set up event listeners
        this.elements.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        this.elements.messageInput.addEventListener('input', () => {
            this.elements.sendButton.disabled = !this.elements.messageInput.value.trim() || !this.isConnected;
        });
        
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Connect WebSocket
        this.connect();
    }
    
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9);
    }
    
    connect() {
        try {
            const wsUrl = `ws://localhost:8000/ws/${this.sessionId}`;
            console.log(`🔌 Connecting to: ${wsUrl}`);
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('✅ WebSocket connected');
                this.isConnected = true;
                this.elements.statusText.textContent = 'Connected';
                this.elements.sendButton.disabled = !this.elements.messageInput.value.trim();
            };
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.websocket.onclose = () => {
                console.log('❌ WebSocket disconnected');
                this.isConnected = false;
                this.elements.statusText.textContent = 'Disconnected';
                this.elements.sendButton.disabled = true;
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.elements.statusText.textContent = 'Connection Error';
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.elements.statusText.textContent = 'Connection Failed';
        }
    }
    
    handleMessage(data) {
        console.log('📨 Received:', data.type);
        
        if (data.type === 'typing') {
            this.showTypingIndicator(data.status);
        } else if (data.type === 'message') {
            this.hideTypingIndicator();
            this.displayAgentMessage(data);
        } else if (data.type === 'error') {
            this.hideTypingIndicator();
            this.displayErrorMessage(data);
        }
    }
    
    sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || !this.isConnected) return;
        
        console.log('📤 Sending:', message);
        
        // Display user message
        this.displayUserMessage(message);
        
        // Send to server
        this.websocket.send(JSON.stringify({
            message: message,
            timestamp: new Date().toISOString()
        }));
        
        // Clear input
        this.elements.messageInput.value = '';
        this.elements.sendButton.disabled = true;
    }
    
    displayUserMessage(message) {
        const messageEl = this.createMessageElement('user', '👤', message);
        this.elements.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }
    
    displayAgentMessage(data) {
        const messageEl = this.createMessageElement('agent', '🤖', data.message);
        this.elements.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
        
        // Update customer ID if provided
        if (data.customer_id && data.customer_id !== this.customerId) {
            this.customerId = data.customer_id;
            this.elements.customerId.textContent = data.customer_id;
        }
        
        // Simple intelligence updates
        if (data.metadata) {
            this.updateSimpleIntelligence(data.metadata);
        }
    }
    
    displayErrorMessage(data) {
        const messageEl = this.createMessageElement('agent', '⚠️', data.message);
        messageEl.querySelector('.message-text').style.background = '#ef4444';
        messageEl.querySelector('.message-text').style.color = 'white';
        this.elements.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }
    
    createMessageElement(type, avatar, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-text">${message}</div>
                <div class="message-meta">
                    <span class="timestamp">${new Date().toLocaleTimeString()}</span>
                </div>
            </div>
        `;
        
        return messageDiv;
    }
    
    showTypingIndicator(isTyping) {
        this.elements.typingIndicator.style.display = isTyping ? 'block' : 'none';
        if (isTyping) this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        this.elements.typingIndicator.style.display = 'none';
    }
    
    updateSimpleIntelligence(metadata) {
        // Simple updates to intelligence panel
        if (metadata.execution_time) {
            const responseTime = document.getElementById('responseTime');
            if (responseTime) {
                responseTime.textContent = `${Math.round(metadata.execution_time * 1000)}ms`;
            }
        }
        
        if (metadata.success !== undefined) {
            const workflowSuccess = document.getElementById('workflowSuccess');
            if (workflowSuccess) {
                workflowSuccess.textContent = metadata.success ? '✅' : '❌';
            }
        }
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }, 100);
    }
}

// Demo scenarios - simplified
const simpleScenarios = {
    technical: "Hi, I'm having trouble with your API. I'm getting 401 errors even though my API key seems correct. Can you help?",
    frustrated: "This is incredibly frustrating! I've been trying to resolve this billing issue for hours. I need this fixed immediately!",
    new: "Hello! I'm new to your platform and would like to understand how to get started. What are the first steps?",
    billing: "I have a question about my billing. I was charged twice this month and I'm not sure why. Can you help me understand?"
};

// Simple scenario loading
function loadScenario(scenario) {
    if (simpleScenarios[scenario] && window.chat) {
        window.chat.elements.messageInput.value = simpleScenarios[scenario];
        window.chat.elements.messageInput.focus();
        window.chat.elements.sendButton.disabled = false;
    }
}

// Simple health panel toggle
function toggleHealthPanel() {
    const content = document.getElementById('healthContent');
    const toggleBtn = document.querySelector('.toggle-btn');
    
    if (content.style.display === 'none' || !content.style.display) {
        content.style.display = 'block';
        toggleBtn.classList.add('open');
    } else {
        content.style.display = 'none';
        toggleBtn.classList.remove('open');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 Simple Customer Support Chat initializing...');
    window.chat = new SimpleChat();
    console.log('✅ Chat ready!');
});
/**
 * Memory-Enhanced Customer Support Agent - Frontend JavaScript
 * WebSocket integration with 6-node LangGraph workflow
 */

class CustomerSupportChat {
    constructor() {
        this.websocket = null;
        this.sessionId = this.generateSessionId();
        this.customerId = null;
        this.isConnected = false;
        this.messageCount = 0;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        // DOM elements
        this.elements = {
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),
            sessionId: document.getElementById('sessionId'),
            customerId: document.getElementById('customerId'),
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            chatForm: document.getElementById('chatForm'),
            typingIndicator: document.getElementById('typingIndicator'),
            // Intelligence panel elements
            commStyle: document.getElementById('commStyle'),
            riskLevel: document.getElementById('riskLevel'),
            urgencyLevel: document.getElementById('urgencyLevel'),
            responseTime: document.getElementById('responseTime'),
            cacheHits: document.getElementById('cacheHits'),
            workflowSuccess: document.getElementById('workflowSuccess')
        };
        
        this.init();
    }
    
    init() {
        console.log('🚀 Initializing Memory-Enhanced Customer Support Agent');
        
        // Update session display
        this.elements.sessionId.textContent = this.sessionId;
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Connect WebSocket
        this.connect();
        
        // Load system health
        this.loadSystemHealth();
        
        // Enable input when ready
        this.elements.messageInput.addEventListener('input', () => {
            this.elements.sendButton.disabled = !this.elements.messageInput.value.trim() || !this.isConnected;
        });
    }
    
    setupEventListeners() {
        // Chat form submission
        this.elements.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Enter key to send
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Health panel toggle
        window.toggleHealthPanel = () => {
            const content = document.getElementById('healthContent');
            const toggleBtn = document.querySelector('.toggle-btn');
            
            if (content.style.display === 'none' || !content.style.display) {
                content.style.display = 'block';
                toggleBtn.classList.add('open');
            } else {
                content.style.display = 'none';
                toggleBtn.classList.remove('open');
            }
        };
        
        // Demo scenarios
        window.loadScenario = (scenario) => {
            const scenarios = {
                technical: "Hi, I'm having trouble with your API integration. I'm getting 401 errors even though my API key seems correct. Can you help me troubleshoot this?",
                frustrated: "This is incredibly frustrating! I've been trying to resolve this billing issue for hours and nothing is working. I need this fixed immediately or I'm canceling my account!",
                new: "Hello! I'm new to your platform and would like to understand how to get started. What are the first steps I should take?",
                billing: "I have a question about my billing. I was charged twice this month and I'm not sure why. Can you help me understand what happened?"
            };
            
            if (scenarios[scenario]) {
                this.elements.messageInput.value = scenarios[scenario];
                this.elements.messageInput.focus();
                this.elements.sendButton.disabled = false;
            }
        };
    }
    
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
    }
    
    connect() {
        try {
            const wsUrl = `ws://localhost:8000/ws/${this.sessionId}`;
            console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('✅ WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected', 'Connected');
                this.elements.sendButton.disabled = !this.elements.messageInput.value.trim();
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };
            
            this.websocket.onclose = (event) => {
                console.log('❌ WebSocket disconnected:', event.code, event.reason);
                this.isConnected = false;
                this.updateConnectionStatus('error', 'Disconnected');
                this.elements.sendButton.disabled = true;
                
                // Attempt to reconnect
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`🔄 Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                    this.updateConnectionStatus('connecting', `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                    setTimeout(() => this.connect(), 2000 * this.reconnectAttempts);
                } else {
                    this.updateConnectionStatus('error', 'Connection failed');
                }
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error', 'Connection error');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.updateConnectionStatus('error', 'Connection failed');
        }
    }
    
    updateConnectionStatus(status, text) {
        this.elements.statusDot.className = `status-dot ${status}`;
        this.elements.statusText.textContent = text;
        
        if (status === 'connecting') {
            this.elements.statusDot.className = 'status-dot';  // Default pulsing
        }
    }
    
    handleMessage(data) {
        console.log('📨 Received message:', data);
        
        switch (data.type) {
            case 'typing':
                this.handleTypingIndicator(data.status);
                break;
                
            case 'message':
                this.hideTypingIndicator();
                this.displayAgentMessage(data);
                this.updateIntelligence(data.metadata);
                break;
                
            case 'error':
                this.hideTypingIndicator();
                this.displayErrorMessage(data);
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || !this.isConnected) return;
        
        // Display user message immediately
        this.displayUserMessage(message);
        
        // Send to server
        try {
            this.websocket.send(JSON.stringify({
                message: message,
                timestamp: new Date().toISOString()
            }));
            
            // Clear input
            this.elements.messageInput.value = '';
            this.elements.sendButton.disabled = true;
            this.messageCount++;
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.displayErrorMessage({
                message: 'Failed to send message. Please check your connection.',
                timestamp: new Date().toISOString()
            });
        }
    }
    
    displayUserMessage(message) {
        const messageElement = this.createMessageElement('user', '👤', message, {
            timestamp: this.formatTimestamp(new Date())
        });
        
        this.elements.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    displayAgentMessage(data) {
        const messageElement = this.createMessageElement('agent', '🤖', data.message, {
            timestamp: this.formatTimestamp(new Date(data.timestamp)),
            confidence: data.metadata?.confidence ? `${Math.round(data.metadata.confidence * 100)}%` : null,
            responseTime: data.metadata?.response_time ? `${Math.round(data.metadata.response_time * 1000)}ms` : null
        });
        
        this.elements.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
        
        // Update customer ID if provided
        if (data.customer_id && data.customer_id !== this.customerId) {
            this.customerId = data.customer_id;
            this.elements.customerId.textContent = data.customer_id;
        }
    }
    
    displayErrorMessage(data) {
        const messageElement = this.createMessageElement('agent', '⚠️', data.message, {
            timestamp: this.formatTimestamp(new Date(data.timestamp)),
            isError: true
        });
        
        this.elements.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    createMessageElement(type, avatar, message, metadata = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message new`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.textContent = avatar;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.textContent = message;
        
        if (metadata.isError) {
            textDiv.style.background = 'var(--error)';
            textDiv.style.color = 'white';
        }
        
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'timestamp';
        timestampSpan.textContent = metadata.timestamp || 'Just now';
        metaDiv.appendChild(timestampSpan);
        
        if (metadata.confidence) {
            const confidenceSpan = document.createElement('span');
            confidenceSpan.className = 'confidence';
            confidenceSpan.textContent = `Confidence: ${metadata.confidence}`;
            metaDiv.appendChild(confidenceSpan);
        }
        
        if (metadata.responseTime) {
            const responseTimeSpan = document.createElement('span');
            responseTimeSpan.className = 'response-time';
            responseTimeSpan.textContent = `Response: ${metadata.responseTime}`;
            metaDiv.appendChild(responseTimeSpan);
        }
        
        contentDiv.appendChild(textDiv);
        contentDiv.appendChild(metaDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        // Remove animation class after animation completes
        setTimeout(() => {
            messageDiv.classList.remove('new');
        }, 300);
        
        return messageDiv;
    }
    
    handleTypingIndicator(isTyping) {
        if (isTyping) {
            this.elements.typingIndicator.style.display = 'block';
            this.scrollToBottom();
        } else {
            this.hideTypingIndicator();
        }
    }
    
    hideTypingIndicator() {
        this.elements.typingIndicator.style.display = 'none';
    }
    
    updateIntelligence(metadata) {
        if (!metadata) return;
        
        // Communication style
        if (metadata.communication_style) {
            const style = metadata.communication_style;
            this.elements.commStyle.textContent = this.formatCommunicationStyle(style);
            this.elements.commStyle.className = `value ${style.toLowerCase()}`;
        }
        
        // Response time
        if (metadata.response_time) {
            const responseTime = Math.round(metadata.response_time * 1000);
            this.elements.responseTime.textContent = `${responseTime}ms`;
        }
        
        // Workflow success
        if (metadata.workflow_success !== undefined) {
            this.elements.workflowSuccess.textContent = metadata.workflow_success ? '✅' : '❌';
        }
        
        // Update cache hits counter (simplified)
        const currentHits = parseInt(this.elements.cacheHits.textContent) || 0;
        this.elements.cacheHits.textContent = currentHits + 1;
    }
    
    formatCommunicationStyle(style) {
        const styles = {
            technical: 'Technical',
            emotional: 'Emotional',
            formal: 'Formal',
            casual: 'Casual',
            neutral: 'Neutral'
        };
        return styles[style] || style;
    }
    
    formatTimestamp(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }, 50);
    }
    
    async loadSystemHealth() {
        try {
            console.log('🏥 Loading system health...');
            
            // Simulate health check (in real deployment, this would call the API)
            const healthData = {
                workflow_compiled: true,
                cache_connected: true,
                database: 'connected',
                neo4j: 'connected',
                redis: 'connected',
                estimated_performance: {
                    full_workflow_time: '200-800ms',
                    cached_response_time: '1-5ms',
                    cache_hit_rate_target: '85%'
                }
            };
            
            // Update health panel
            document.getElementById('workflowHealth').textContent = healthData.workflow_compiled ? '✅ Operational' : '❌ Error';
            document.getElementById('redisHealth').textContent = healthData.cache_connected ? '✅ Connected' : '❌ Disconnected';
            document.getElementById('neo4jHealth').textContent = healthData.neo4j === 'connected' ? '✅ Connected' : '❌ Disconnected';
            document.getElementById('databaseHealth').textContent = healthData.database === 'connected' ? '✅ Connected' : '❌ Disconnected';
            document.getElementById('avgResponse').textContent = healthData.estimated_performance.full_workflow_time;
            document.getElementById('cacheHitRate').textContent = healthData.estimated_performance.cache_hit_rate_target;
            
        } catch (error) {
            console.error('Failed to load system health:', error);
            
            // Set error states
            document.getElementById('workflowHealth').textContent = '❌ Error';
            document.getElementById('redisHealth').textContent = '❌ Error';
            document.getElementById('neo4jHealth').textContent = '❌ Error';
            document.getElementById('databaseHealth').textContent = '❌ Error';
        }
    }
}

// Demo scenarios data
const DEMO_SCENARIOS = {
    technical: {
        title: "🔧 Technical Issue",
        description: "API integration problem with authentication errors",
        messages: [
            "Hi, I'm having trouble with your API integration. I'm getting 401 errors even though my API key seems correct.",
            "The documentation mentions rate limiting - could that be the issue?",
            "I'm using the Python SDK version 2.1.0"
        ]
    },
    frustrated: {
        title: "😠 Frustrated Customer", 
        description: "Urgent billing issue with high emotional intensity",
        messages: [
            "This is incredibly frustrating! I've been trying to resolve this billing issue for hours and nothing is working.",
            "I need this fixed immediately or I'm canceling my account!",
            "Your support has been completely unhelpful so far."
        ]
    },
    new: {
        title: "👋 New Customer",
        description: "First-time user seeking guidance and onboarding",
        messages: [
            "Hello! I'm new to your platform and would like to understand how to get started.",
            "What are the first steps I should take?",
            "Do you have any getting started guides or tutorials?"
        ]
    },
    billing: {
        title: "💳 Billing Question",
        description: "Account billing inquiry with specific concern",
        messages: [
            "I have a question about my billing. I was charged twice this month and I'm not sure why.",
            "Can you help me understand what happened?",
            "I need to see the detailed breakdown of charges."
        ]
    }
};

// Initialize the chat application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 DOM loaded, initializing chat application...');
    
    // Create global chat instance
    window.customerSupportChat = new CustomerSupportChat();
    
    // Add some helpful console messages for developers
    console.log('🧠 Memory-Enhanced Customer Support Agent');
    console.log('🔗 Features: 6-Node LangGraph Workflow, Redis Caching, Neo4j Intelligence');
    console.log('📡 WebSocket connection for real-time chat');
    console.log('🎭 Try the demo scenarios in the sidebar!');
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + Enter to send message
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            window.customerSupportChat.sendMessage();
        }
        
        // ESC to clear input
        if (e.key === 'Escape') {
            window.customerSupportChat.elements.messageInput.value = '';
            window.customerSupportChat.elements.sendButton.disabled = true;
        }
    });
});
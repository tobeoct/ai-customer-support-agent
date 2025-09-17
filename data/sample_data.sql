-- Sample data for Memory-Enhanced Customer Support Agent

-- Sample customers with different classification profiles
INSERT INTO customers (session_id, name, email, phone, relationship_stage, communication_style, urgency_level, satisfaction_score) VALUES
('session_001', 'John Smith', 'john.smith@email.com', '+1234567890', 'returning', 'formal', 'medium', 0.85),
('session_002', 'Sarah Johnson', 'sarah.j@email.com', '+1234567891', 'new', 'casual', 'low', 0.75),
('session_003', 'Mike Chen', 'mike.chen@techcorp.com', '+1234567892', 'vip', 'technical', 'high', 0.95),
('session_004', 'Emily Davis', 'emily.davis@email.com', '+1234567893', 'churned', 'emotional', 'critical', 0.45);

-- Sample knowledge base documents
INSERT INTO documents (title, content, document_type, category, keywords) VALUES
('Billing FAQ', 'Common questions about billing, payments, and refunds. We accept all major credit cards and PayPal. Billing cycles are monthly on the anniversary of signup.', 'faq', 'billing', 'billing,payment,refund,credit card,paypal'),
('Technical Support Guide', 'Step-by-step troubleshooting for common technical issues. First, check your internet connection. Then restart the application. If issues persist, contact support.', 'procedure', 'technical', 'troubleshooting,technical,internet,restart,support'),
('Product Features Overview', 'Comprehensive guide to all product features including advanced analytics, custom dashboards, and API integrations.', 'product_info', 'sales', 'features,analytics,dashboard,api,integration'),
('Privacy Policy', 'Our commitment to protecting your data. We collect minimal information and never share personal data with third parties without explicit consent.', 'policy', 'legal', 'privacy,data,protection,consent,legal');

-- Sample conversations and messages
INSERT INTO conversations (customer_id, session_id, topic, status, priority, summary) VALUES
(1, 'session_001', 'Billing Question', 'resolved', 'medium', 'Customer asked about payment method change'),
(2, 'session_002', 'Feature Request', 'active', 'low', 'Customer interested in API access'),
(3, 'session_003', 'Technical Issue', 'escalated', 'high', 'Complex integration problem requiring engineering support'),
(4, 'session_004', 'Cancellation Request', 'resolved', 'critical', 'Customer dissatisfied with service quality');

-- Sample messages for conversations
INSERT INTO messages (conversation_id, content, message_type, intent, sentiment) VALUES
(1, 'Hi, I need to update my payment method', 'user', 'request', 'neutral'),
(1, 'I can help you update your payment method. Please go to Account Settings > Billing.', 'assistant', 'response', 'positive'),
(1, 'Perfect, thank you!', 'user', 'gratitude', 'positive'),

(2, 'Do you have an API for integrations?', 'user', 'question', 'neutral'),
(2, 'Yes! We offer a comprehensive REST API. Would you like me to send you the documentation?', 'assistant', 'response', 'positive'),

(3, 'The API integration is failing with error 500', 'user', 'complaint', 'negative'),
(3, 'I apologize for the issue. Let me escalate this to our technical team immediately.', 'assistant', 'response', 'neutral'),

(4, 'I want to cancel my subscription', 'user', 'request', 'negative'),
(4, 'I understand your concern. Let me help you with the cancellation process and see if we can address any issues.', 'assistant', 'response', 'neutral');

-- Sample interaction records
INSERT INTO interactions (customer_id, interaction_type, channel, outcome, response_time_seconds, resolution_time_seconds) VALUES
(1, 'chat', 'web', 'resolved', 15.5, 120.0),
(2, 'chat', 'web', 'pending', 8.2, NULL),
(3, 'chat', 'web', 'escalated', 25.1, NULL),
(4, 'chat', 'web', 'resolved', 12.3, 300.5);

-- Sample conversation memory
INSERT INTO conversation_memory (customer_id, memory_type, content, importance, source_conversation_id, tags) VALUES
(1, 'preference', 'Prefers email notifications over SMS', 0.7, 1, 'notification,preference'),
(2, 'context', 'Software developer interested in API integrations', 0.9, 2, 'developer,api,integration'),
(3, 'issue', 'Has complex enterprise integration requirements', 0.8, 3, 'enterprise,integration,technical'),
(4, 'note', 'Customer expressed frustration with recent service changes', 0.6, 4, 'feedback,service,frustration');
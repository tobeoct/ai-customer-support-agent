"""
Simple LangGraph Workflow Agent - Memory-Enhanced Customer Support
Core 6-node workflow with basic logging
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.services.customer import customer_service
from app.services.classification import classification_service
from app.services.rag import rag_service
from app.services.graph import graph_service
from app.services.intelligence import intelligence_service
from app.services.reinforcement_learning import get_rl_service, RLState, RLReward, RewardType, ActionType
from app.services.feedback_system import feedback_collector, generate_session_feedback
from app.core.llm import llm_client
from app.models.schemas import (
    CommunicationStyle, UrgencyLevel, RelationshipStage, 
    SentimentType, MessageType
)


class SimpleWorkflowState:
    """Simple state object for workflow"""
    
    def __init__(self):
        self.customer_id: Optional[int] = None
        self.session_id: Optional[str] = None
        self.user_query: str = ""
        self.customer_profile: Dict[str, Any] = {}
        self.context_documents: list = []
        self.final_response: str = ""
        self.start_time = datetime.now()
        self.db_session = None
        # RL-specific attributes
        self.rl_state: Optional[RLState] = None
        self.rl_action = None
        self.sentiment_score: float = 0.0
        self.communication_style: CommunicationStyle = CommunicationStyle.NEUTRAL
        self.urgency_level: UrgencyLevel = UrgencyLevel.MEDIUM


class SimpleCustomerSupportAgent:
    """Simple customer support agent with 6-node workflow"""
    
    def __init__(self):
        logger.info("🤖 Initializing Simple Customer Support Agent")
    
    async def process_query(self, user_query: str, session_id: str = None, customer_id: int = None, db_session = None) -> Dict[str, Any]:
        """Process customer query through simple 6-node workflow"""
        
        logger.info(f"🚀 Processing query: '{user_query[:50]}...'")
        
        # Initialize state
        state = SimpleWorkflowState()
        state.user_query = user_query
        state.session_id = session_id or f"session_{datetime.now().timestamp()}"
        state.customer_id = customer_id
        state.db_session = db_session
        
        # Initialize feedback collection for this session
        feedback_collector.start_session(state.session_id)
        feedback_collector.record_customer_message(state.session_id, user_query)
        
        try:
            # Node 1: Load Customer
            logger.info("📋 Node 1: Loading customer...")
            await self._load_customer(state)
            
            # Node 2: Classify Customer
            logger.info("🔍 Node 2: Classifying customer...")
            await self._classify_customer(state)
            
            # Node 3: Get Context
            logger.info("📚 Node 3: Getting context...")
            await self._get_context(state)
            
            # Node 4: Analyze Query
            logger.info("🤔 Node 4: Analyzing query...")
            await self._analyze_query(state)
            
            # Node 5: Generate Response
            logger.info("🤖 Node 5: Generating response...")
            await self._generate_response(state)
            
            # Node 6: Finalize
            logger.info("✨ Node 6: Finalizing...")
            await self._finalize_response(state)
            
            # Record response time for feedback
            feedback_collector.record_agent_response_time(state.session_id)
            
            # Calculate execution time
            execution_time = (datetime.now() - state.start_time).total_seconds()
            
            # Generate automatic feedback for RL system
            if state.rl_state and state.rl_action:
                asyncio.create_task(self._provide_automatic_feedback(state))
            
            logger.info(f"✅ Workflow completed in {execution_time:.2f}s")
            
            return {
                "response": state.final_response,
                "customer_id": state.customer_id,
                "session_id": state.session_id,
                "execution_time": execution_time,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            return {
                "response": "I apologize, but I'm having technical difficulties. Let me connect you with a human agent.",
                "error": str(e),
                "success": False
            }
    
    async def _load_customer(self, state: SimpleWorkflowState):
        """Node 1: Load customer profile"""
        try:
            if state.customer_id:
                customer = await customer_service.get_customer_by_id(state.customer_id, state.db_session)
            elif state.session_id:
                customer = await customer_service.get_customer_by_session(state.session_id, state.db_session)
            else:
                # Create new customer
                from app.models.schemas import CustomerCreate
                new_customer = CustomerCreate(
                    session_id=state.session_id or f"session_{datetime.now().timestamp()}",
                    name="Anonymous User"
                )
                customer = await customer_service.create_customer(new_customer, state.db_session)
                state.customer_id = customer.id
            
            if customer:
                state.customer_id = customer.id
                state.customer_profile = {
                    "customer_id": customer.id,
                    "name": customer.name,
                    "communication_style": customer.communication_style,
                    "relationship_stage": customer.relationship_stage
                }
                logger.info(f"✅ Customer loaded: {customer.name}")
            
        except Exception as e:
            logger.error(f"Failed to load customer: {e}")
            state.customer_profile = {"customer_id": None, "name": "Anonymous"}
    
    async def _classify_customer(self, state: SimpleWorkflowState):
        """Node 2: Classify customer behavior and communication style"""
        try:
            if state.customer_id:
                classification = await classification_service.classify_customer_comprehensive(
                    state.customer_id, state.db_session
                )
                
                # Extract key insights
                comm_style = classification.get("communication_style", {}).get("primary_style", CommunicationStyle.NEUTRAL.value)
                risk_level = classification.get("risk_assessment", {}).get("risk_level", UrgencyLevel.LOW.value)
                
                state.customer_profile.update({
                    "communication_style": comm_style,
                    "risk_level": risk_level
                })
                
                # Store for RL
                state.communication_style = CommunicationStyle(comm_style)
                
                # Simple sentiment analysis for RL
                query_lower = state.user_query.lower()
                if any(word in query_lower for word in ["frustrated", "angry", "terrible", "awful"]):
                    state.sentiment_score = -0.8
                elif any(word in query_lower for word in ["annoyed", "problem", "issue"]):
                    state.sentiment_score = -0.3
                elif any(word in query_lower for word in ["great", "excellent", "love"]):
                    state.sentiment_score = 0.8
                else:
                    state.sentiment_score = 0.0
                
                logger.info(f"✅ Customer classified: {comm_style} style, {risk_level} risk, sentiment: {state.sentiment_score}")
            
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            state.customer_profile["communication_style"] = CommunicationStyle.NEUTRAL.value
    
    async def _get_context(self, state: SimpleWorkflowState):
        """Node 3: Get relevant context from documents and graph"""
        try:
            # Get relevant documents
            docs = await rag_service.search_documents(
                state.user_query, limit=3, db_session=state.db_session
            )
            state.context_documents = docs
            
            # Get similar customers (if available)
            if state.customer_id:
                similar = await graph_service.find_similar_customers(state.customer_id, limit=2)
                state.customer_profile["similar_customers"] = len(similar)
            
            logger.info(f"✅ Context gathered: {len(docs)} documents")
            
        except Exception as e:
            logger.error(f"Context gathering failed: {e}")
            state.context_documents = []
    
    async def _analyze_query(self, state: SimpleWorkflowState):
        """Node 4: Simple query analysis"""
        try:
            # Simple sentiment analysis
            query_lower = state.user_query.lower()
            
            if any(word in query_lower for word in ["urgent", "immediately", "asap", "critical"]):
                urgency = UrgencyLevel.HIGH.value
            elif any(word in query_lower for word in ["frustrated", "angry", "terrible", "awful"]):
                urgency = UrgencyLevel.HIGH.value
            elif any(word in query_lower for word in ["please", "help", "question"]):
                urgency = UrgencyLevel.MEDIUM.value
            else:
                urgency = UrgencyLevel.LOW.value
            
            state.customer_profile["urgency"] = urgency
            state.urgency_level = UrgencyLevel(urgency)
            
            logger.info(f"✅ Query analyzed: {urgency} urgency")
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            state.customer_profile["urgency"] = UrgencyLevel.MEDIUM.value
    
    async def _generate_response(self, state: SimpleWorkflowState):
        """Node 5: Generate AI response using OpenAI with RL optimization"""
        try:
            # Create RL state for decision making
            state.rl_state = RLState(
                communication_style=state.communication_style,
                urgency_level=state.urgency_level,
                customer_sentiment=state.sentiment_score,
                interaction_count=len(state.customer_profile.get("interaction_history", [])),
                time_of_day=datetime.now().hour,
                issue_category="general",  # Could be enhanced with classification
                customer_tier=state.customer_profile.get("tier", "regular")
            )
            
            # Get RL-optimized action
            rl_service = await get_rl_service()
            state.rl_action = await rl_service.get_optimal_action(state.rl_state)
            
            logger.info(f"🧠 RL recommends: {state.rl_action.action_type} (confidence: {state.rl_action.confidence:.2f})")
            
            # Build context for AI with RL guidance
            context = self._build_context_for_ai_with_rl(state)
            
            # Try OpenAI if available
            if llm_client.client:
                messages = [
                    {"role": "system", "content": context},
                    {"role": "user", "content": state.user_query}
                ]
                
                response = llm_client.generate_response(messages)
                if response:
                    state.final_response = response
                    logger.info("✅ AI response generated with RL guidance")
                    return
            
            # Fallback response with RL guidance
            state.final_response = self._generate_rl_guided_fallback_response(state)
            logger.info("✅ RL-guided fallback response generated")
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state.final_response = self._generate_fallback_response(state)
    
    async def _finalize_response(self, state: SimpleWorkflowState):
        """Node 6: Finalize and personalize response"""
        try:
            # Simple personalization based on customer profile
            comm_style = state.customer_profile.get("communication_style", CommunicationStyle.NEUTRAL.value)
            urgency = state.customer_profile.get("urgency", UrgencyLevel.MEDIUM.value)
            
            # Add greeting based on style
            if comm_style == CommunicationStyle.FORMAL.value:
                greeting = "Thank you for contacting our support team."
            elif comm_style == CommunicationStyle.CASUAL.value:
                greeting = "Hi there! Thanks for reaching out."
            else:
                greeting = "Hello! I'm here to help."
            
            # Add urgency handling
            if urgency == UrgencyLevel.HIGH.value:
                urgency_note = " I understand this is urgent and I'll prioritize your request."
            else:
                urgency_note = ""
            
            # Combine final response
            final_parts = [greeting + urgency_note, state.final_response]
            
            # Add helpful closing
            closing = "Is there anything else I can help you with today?"
            final_parts.append(closing)
            
            state.final_response = "\n\n".join(final_parts)
            
            logger.info("✅ Response finalized and personalized")
            
        except Exception as e:
            logger.error(f"Response finalization failed: {e}")
            # Keep original response if finalization fails
    
    def _build_context_for_ai(self, state: SimpleWorkflowState) -> str:
        """Build context string for AI model"""
        
        context_parts = [
            "You are a helpful customer support agent.",
            f"Customer communication style: {state.customer_profile.get('communication_style', 'neutral')}",
            f"Query urgency: {state.customer_profile.get('urgency', 'medium')}"
        ]
        
        # Add document context if available
        if state.context_documents:
            context_parts.append("Relevant information:")
            for doc in state.context_documents[:2]:  # Top 2 docs
                context_parts.append(f"- {doc.get('title', 'Document')}: {doc.get('content', '')[:200]}...")
        
        context_parts.extend([
            "Provide a helpful, accurate response.",
            "Be concise but thorough.",
            "Match the customer's communication style."
        ])
        
        return "\n".join(context_parts)
    
    def _generate_fallback_response(self, state: SimpleWorkflowState) -> str:
        """Generate simple fallback response when AI is not available"""
        
        comm_style = state.customer_profile.get("communication_style", CommunicationStyle.NEUTRAL.value)
        urgency = state.customer_profile.get("urgency", UrgencyLevel.MEDIUM.value)
        
        if urgency == UrgencyLevel.HIGH.value:
            base = "I understand this is urgent. Let me connect you with a specialist who can provide immediate assistance."
        elif comm_style == CommunicationStyle.TECHNICAL.value:
            base = "I'd be happy to help with your technical question. Let me get you connected with our technical support team."
        elif comm_style == CommunicationStyle.FORMAL.value:
            base = "Thank you for your inquiry. I will ensure you receive the proper assistance for your request."
        else:
            base = "Thanks for reaching out! I want to make sure you get the best help possible."
        
        return base + " A human agent will be with you shortly."
    
    def _build_context_for_ai_with_rl(self, state: SimpleWorkflowState) -> str:
        """Build context string for AI model with RL guidance"""
        
        rl_action = state.rl_action
        context_parts = [
            "You are a helpful customer support agent with AI-powered response optimization.",
            f"Customer communication style: {state.communication_style.value}",
            f"Query urgency: {state.urgency_level.value}",
            f"Customer sentiment: {state.sentiment_score:.1f} (-1=negative, +1=positive)",
            f"Recommended response approach: {rl_action.action_type.value}",
            f"Response strategy: {rl_action.response_strategy}",
            f"Personalization level: {rl_action.personalization_level:.1f} (0=generic, 1=highly personalized)"
        ]
        
        # Add RL-specific guidance based on action type
        if rl_action.action_type.value == "empathetic":
            context_parts.append("GUIDANCE: Use empathetic language, acknowledge emotions, show understanding.")
        elif rl_action.action_type.value == "technical":
            context_parts.append("GUIDANCE: Provide detailed technical information, use precise terminology.")
        elif rl_action.action_type.value == "formal":
            context_parts.append("GUIDANCE: Maintain professional tone, use structured responses.")
        elif rl_action.action_type.value == "casual":
            context_parts.append("GUIDANCE: Use friendly, conversational tone, keep it simple.")
        elif rl_action.action_type.value == "escalation":
            context_parts.append("GUIDANCE: Prepare for escalation, gather all relevant information.")
        
        # Add document context if available
        if state.context_documents:
            context_parts.append("Relevant information:")
            for doc in state.context_documents[:2]:  # Top 2 docs
                context_parts.append(f"- {doc.get('title', 'Document')}: {doc.get('content', '')[:200]}...")
        
        context_parts.extend([
            "Provide a helpful, accurate response following the recommended approach.",
            "Adapt your response style based on the guidance above.",
            f"AI confidence in recommendation: {rl_action.confidence:.1f}"
        ])
        
        return "\n".join(context_parts)
    
    def _generate_rl_guided_fallback_response(self, state: SimpleWorkflowState) -> str:
        """Generate RL-guided fallback response when AI is not available"""
        
        rl_action = state.rl_action
        action_type = rl_action.action_type.value
        urgency = state.urgency_level.value
        sentiment = state.sentiment_score
        
        # Base responses guided by RL action type
        responses = {
            "empathetic": {
                "high": "I can see this is really important to you, and I completely understand your urgency. Let me get you connected with someone who can provide immediate, personal assistance right away.",
                "medium": "I hear you and want to make sure we address your concern properly. You're definitely in the right place for help.",
                "low": "Thanks for reaching out - I appreciate you taking the time to contact us. Let's make sure we get this sorted out for you."
            },
            "technical": {
                "high": "I understand you need technical assistance urgently. Let me route you directly to our technical specialists who have the expertise to resolve this efficiently.",
                "medium": "For your technical inquiry, I'll connect you with our technical support team who can provide detailed guidance and solutions.",
                "low": "I see you have a technical question. Our technical support team will be able to provide you with comprehensive assistance."
            },
            "formal": {
                "high": "I acknowledge the urgent nature of your request. You will be connected with a senior specialist immediately to address this matter with the highest priority.",
                "medium": "Thank you for your inquiry. I will ensure you are properly connected with the appropriate department to resolve your request.",
                "low": "I appreciate you contacting us regarding this matter. A qualified representative will assist you with your request shortly."
            },
            "casual": {
                "high": "Hey, I can see this needs immediate attention! Let me get you connected with someone who can jump right on this for you.",
                "medium": "Thanks for reaching out! Let's get you the help you need - I'll connect you with the right person.",
                "low": "Hi there! Happy to help. Let me put you in touch with someone who can take great care of this for you."
            },
            "escalation": {
                "high": "I understand the critical nature of this issue. I'm immediately escalating this to our senior team for priority handling.",
                "medium": "I want to make sure this gets the attention it deserves. Let me connect you with a specialist who can provide comprehensive assistance.",
                "low": "To ensure you get the best possible resolution, I'm connecting you with a specialist who can give this proper focus."
            }
        }
        
        # Adjust based on sentiment
        if sentiment < -0.5:  # Negative sentiment
            prefix = "I'm really sorry you're experiencing this issue. "
        elif sentiment > 0.5:  # Positive sentiment  
            prefix = "I'm glad you reached out! "
        else:
            prefix = ""
        
        base_response = responses.get(action_type, responses["empathetic"]).get(urgency, responses["empathetic"]["medium"])
        
        return prefix + base_response
    
    async def provide_rl_feedback(self, state: SimpleWorkflowState, satisfaction_score: float):
        """Provide feedback to RL system based on interaction outcome"""
        try:
            if state.rl_state and state.rl_action:
                reward = RLReward(
                    reward_type=RewardType.CUSTOMER_SATISFACTION,
                    value=satisfaction_score,
                    timestamp=datetime.now(),
                    customer_id=str(state.customer_id),
                    session_id=state.session_id
                )
                
                rl_service = await get_rl_service()
                await rl_service.provide_feedback(state.rl_state, state.rl_action, reward)
                logger.info(f"🔄 RL feedback provided: {satisfaction_score}")
                
        except Exception as e:
            logger.error(f"Failed to provide RL feedback: {e}")
    
    async def _provide_automatic_feedback(self, state: SimpleWorkflowState):
        """
        Generate automatic feedback based on interaction analysis
        This runs in the background after response generation
        """
        try:
            # Get session metrics
            metrics = feedback_collector.get_session_metrics(state.session_id)
            if not metrics:
                logger.warning(f"No metrics available for session {state.session_id}")
                return
            
            # Generate multiple reward signals
            rewards = await generate_session_feedback(state.session_id)
            
            # Provide each reward to the RL system
            rl_service = await get_rl_service()
            for reward in rewards:
                if state.rl_state and state.rl_action:
                    # Provide feedback with the original state and action
                    await rl_service.provide_feedback(state.rl_state, state.rl_action, reward)
                    logger.info(f"🔄 Auto-feedback: {reward.reward_type.value} = {reward.value:.2f}")
            
            # Simulate next state for Q-learning (simplified)
            if state.rl_state and len(rewards) > 0:
                # Create a "next state" representing the post-interaction state
                next_state = RLState(
                    communication_style=state.rl_state.communication_style,
                    urgency_level=UrgencyLevel.LOW,  # Assume resolved
                    customer_sentiment=max(-1.0, state.rl_state.customer_sentiment + 0.2),  # Slight improvement
                    interaction_count=state.rl_state.interaction_count + 1,
                    time_of_day=state.rl_state.time_of_day,
                    issue_category=state.rl_state.issue_category,
                    customer_tier=state.rl_state.customer_tier
                )
                
                # Update Q-learning with state transition
                best_reward = max(rewards, key=lambda r: r.value)
                action_idx = list(ActionType).index(state.rl_action.action_type)
                rl_service.q_agent.update(state.rl_state, action_idx, best_reward.value, next_state)
                
                logger.info(f"🧠 Q-learning updated with transition reward: {best_reward.value:.2f}")
                
        except Exception as e:
            logger.error(f"Failed to provide automatic feedback: {e}")


# Global instance
simple_agent = SimpleCustomerSupportAgent()
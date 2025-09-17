"""
Automatic Feedback Generation System for Reinforcement Learning

This module implements multiple feedback mechanisms to automatically
generate rewards for the RL system based on customer interactions.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.models.schemas import MessageType, UrgencyLevel, CommunicationStyle
from app.services.reinforcement_learning import RLReward, RewardType, get_rl_service
from app.core.database import get_db_session
from app.core.llm import llm_client

logger = logging.getLogger(__name__)

@dataclass
class InteractionMetrics:
    """Metrics collected during customer interaction"""
    response_time: float  # seconds
    message_length: int
    follow_up_questions: int
    escalation_requested: bool
    session_ended_by_customer: bool
    customer_thanked_agent: bool
    customer_expressed_frustration: bool
    issue_resolution_keywords: bool

class AutomaticFeedbackGenerator:
    """Generates automatic rewards based on interaction analysis"""
    
    def __init__(self):
        self.satisfaction_keywords = {
            "positive": ["thank", "thanks", "great", "excellent", "perfect", "solved", "fixed", "helpful", "amazing"],
            "negative": ["terrible", "awful", "useless", "frustrated", "angry", "disappointed", "horrible", "worst"]
        }
        
        self.resolution_keywords = [
            "solved", "fixed", "resolved", "working", "success", "complete", "done", "finished"
        ]
        
        self.escalation_keywords = [
            "manager", "supervisor", "escalate", "complaint", "speak to someone else", "transfer"
        ]
    
    async def analyze_interaction_and_generate_feedback(
        self, 
        session_id: str,
        customer_messages: List[str],
        agent_responses: List[str],
        interaction_metrics: InteractionMetrics
    ) -> List[RLReward]:
        """
        Analyze complete interaction and generate multiple reward signals
        """
        rewards = []
        
        try:
            # 1. Sentiment-based satisfaction score
            satisfaction_reward = await self._calculate_satisfaction_reward(
                customer_messages, interaction_metrics
            )
            if satisfaction_reward:
                rewards.append(satisfaction_reward)
            
            # 2. Response time efficiency
            if interaction_metrics.response_time < 3.0:  # Under 3 seconds
                rewards.append(RLReward(
                    reward_type=RewardType.RESPONSE_TIME,
                    value=min(1.0, 5.0 / interaction_metrics.response_time),  # Faster = higher reward
                    timestamp=datetime.now(),
                    customer_id="auto_feedback",
                    session_id=session_id
                ))
            
            # 3. Escalation avoidance
            if not interaction_metrics.escalation_requested:
                rewards.append(RLReward(
                    reward_type=RewardType.ESCALATION_AVOIDED,
                    value=0.8,
                    timestamp=datetime.now(),
                    customer_id="auto_feedback", 
                    session_id=session_id
                ))
            
            # 4. Resolution success
            if interaction_metrics.issue_resolution_keywords:
                rewards.append(RLReward(
                    reward_type=RewardType.RESOLUTION_SUCCESS,
                    value=0.9,
                    timestamp=datetime.now(),
                    customer_id="auto_feedback",
                    session_id=session_id
                ))
            
            # 5. Follow-up reduction (fewer questions = better initial response)
            if interaction_metrics.follow_up_questions <= 1:
                rewards.append(RLReward(
                    reward_type=RewardType.FOLLOW_UP_REDUCED,
                    value=0.7,
                    timestamp=datetime.now(),
                    customer_id="auto_feedback",
                    session_id=session_id
                ))
            
            return rewards
            
        except Exception as e:
            logger.error(f"Error generating automatic feedback: {e}")
            return []
    
    async def _calculate_satisfaction_reward(
        self,
        customer_messages: List[str],
        metrics: InteractionMetrics
    ) -> Optional[RLReward]:
        """Calculate satisfaction score from customer messages and behavior"""
        
        if not customer_messages:
            return None
        
        # Combine all customer messages
        full_conversation = " ".join(customer_messages).lower()
        
        # Count positive and negative sentiment indicators
        positive_count = sum(1 for word in self.satisfaction_keywords["positive"] 
                           if word in full_conversation)
        negative_count = sum(1 for word in self.satisfaction_keywords["negative"]
                           if word in full_conversation)
        
        # Behavioral indicators
        behavioral_score = 0.5  # neutral baseline
        
        if metrics.customer_thanked_agent:
            behavioral_score += 0.3
        
        if metrics.customer_expressed_frustration:
            behavioral_score -= 0.4
        
        if metrics.session_ended_by_customer and not metrics.escalation_requested:
            behavioral_score += 0.2  # Natural ending suggests satisfaction
        
        # Combine sentiment and behavioral scores
        sentiment_score = 0.5  # neutral baseline
        
        if positive_count > negative_count:
            sentiment_score = min(1.0, 0.5 + (positive_count - negative_count) * 0.1)
        elif negative_count > positive_count:
            sentiment_score = max(0.0, 0.5 - (negative_count - positive_count) * 0.1)
        
        # Final satisfaction score (weighted average)
        final_score = (sentiment_score * 0.6) + (behavioral_score * 0.4)
        final_score = max(0.0, min(1.0, final_score))
        
        return RLReward(
            reward_type=RewardType.CUSTOMER_SATISFACTION,
            value=final_score,
            timestamp=datetime.now(),
            customer_id="auto_feedback",
            session_id="derived_from_interaction"
        )

class RealTimeFeedbackCollector:
    """Collects feedback signals during live conversations"""
    
    def __init__(self):
        self.active_sessions: Dict[str, InteractionMetrics] = {}
        self.message_timestamps: Dict[str, datetime] = {}
    
    def start_session(self, session_id: str):
        """Initialize tracking for a new session"""
        self.active_sessions[session_id] = InteractionMetrics(
            response_time=0.0,
            message_length=0,
            follow_up_questions=0,
            escalation_requested=False,
            session_ended_by_customer=False,
            customer_thanked_agent=False,
            customer_expressed_frustration=False,
            issue_resolution_keywords=False
        )
        self.message_timestamps[session_id] = datetime.now()
    
    def record_customer_message(self, session_id: str, message: str):
        """Record and analyze customer message"""
        if session_id not in self.active_sessions:
            self.start_session(session_id)
        
        metrics = self.active_sessions[session_id]
        message_lower = message.lower()
        
        # Check for various indicators
        if any(word in message_lower for word in ["thank", "thanks"]):
            metrics.customer_thanked_agent = True
        
        if any(word in message_lower for word in ["frustrated", "angry", "terrible"]):
            metrics.customer_expressed_frustration = True
        
        if any(word in message_lower for word in ["manager", "escalate", "supervisor"]):
            metrics.escalation_requested = True
        
        if any(word in message_lower for word in ["solved", "fixed", "working", "resolved"]):
            metrics.issue_resolution_keywords = True
        
        # Count follow-up questions
        if "?" in message:
            metrics.follow_up_questions += 1
        
        metrics.message_length += len(message)
    
    def record_agent_response_time(self, session_id: str):
        """Record how long it took to generate agent response"""
        if session_id in self.message_timestamps:
            response_time = (datetime.now() - self.message_timestamps[session_id]).total_seconds()
            if session_id in self.active_sessions:
                self.active_sessions[session_id].response_time = response_time
        
        # Update timestamp for next measurement
        self.message_timestamps[session_id] = datetime.now()
    
    def end_session(self, session_id: str, ended_by_customer: bool = True):
        """Mark session as ended and potentially generate feedback"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].session_ended_by_customer = ended_by_customer
    
    def get_session_metrics(self, session_id: str) -> Optional[InteractionMetrics]:
        """Get collected metrics for a session"""
        return self.active_sessions.get(session_id)

class LLMBasedFeedbackGenerator:
    """Uses LLM to analyze conversation quality and generate feedback"""
    
    async def analyze_conversation_quality(
        self,
        customer_messages: List[str],
        agent_responses: List[str]
    ) -> float:
        """Use LLM to analyze overall conversation quality"""
        
        if not llm_client.client or not customer_messages or not agent_responses:
            return 0.5  # neutral score if no LLM available
        
        # Build conversation context
        conversation = []
        for i, (customer_msg, agent_msg) in enumerate(zip(customer_messages, agent_responses)):
            conversation.append(f"Customer: {customer_msg}")
            conversation.append(f"Agent: {agent_msg}")
        
        conversation_text = "\n".join(conversation)
        
        analysis_prompt = f"""
        Analyze this customer support conversation and rate the agent's performance:

        {conversation_text}

        Rate the agent's performance on a scale of 0.0 to 1.0 based on:
        1. Helpfulness and relevance of responses
        2. Appropriate tone and empathy
        3. Problem-solving effectiveness
        4. Professional communication
        5. Customer satisfaction indicators

        Respond with only a number between 0.0 and 1.0 (e.g., 0.85)
        """
        
        try:
            messages = [{"role": "user", "content": analysis_prompt}]
            response = llm_client.generate_response(messages)
            
            if response:
                # Extract numerical score
                import re
                score_match = re.search(r'(\d+\.?\d*)', response)
                if score_match:
                    score = float(score_match.group(1))
                    return max(0.0, min(1.0, score))
            
            return 0.5  # default if parsing fails
            
        except Exception as e:
            logger.error(f"LLM feedback analysis failed: {e}")
            return 0.5

# Global instances
feedback_generator = AutomaticFeedbackGenerator()
feedback_collector = RealTimeFeedbackCollector()
llm_feedback_generator = LLMBasedFeedbackGenerator()

async def generate_session_feedback(session_id: str) -> List[RLReward]:
    """
    Generate comprehensive feedback for a completed session
    
    This is the main function called after customer interactions
    to provide rewards to the RL system.
    """
    try:
        metrics = feedback_collector.get_session_metrics(session_id)
        if not metrics:
            logger.warning(f"No metrics found for session {session_id}")
            return []
        
        # Get conversation history (would typically come from database)
        customer_messages = ["Hello, I need help with my account"]  # Placeholder
        agent_responses = ["I'd be happy to help you with your account"]  # Placeholder
        
        # Generate automatic feedback
        rewards = await feedback_generator.analyze_interaction_and_generate_feedback(
            session_id, customer_messages, agent_responses, metrics
        )
        
        # Add LLM-based quality assessment
        llm_score = await llm_feedback_generator.analyze_conversation_quality(
            customer_messages, agent_responses
        )
        
        if llm_score != 0.5:  # Only add if we got a real assessment
            rewards.append(RLReward(
                reward_type=RewardType.CUSTOMER_SATISFACTION,
                value=llm_score,
                timestamp=datetime.now(),
                customer_id="llm_analysis",
                session_id=session_id
            ))
        
        # Send rewards to RL system
        rl_service = await get_rl_service()
        for reward in rewards:
            # Note: We'd need the original state and action to do proper RL updates
            logger.info(f"Generated feedback: {reward.reward_type} = {reward.value:.2f}")
        
        return rewards
        
    except Exception as e:
        logger.error(f"Error generating session feedback: {e}")
        return []
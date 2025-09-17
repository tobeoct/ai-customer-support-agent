"""
Reinforcement Learning Service for Response Optimization

This module implements a Multi-Armed Bandit and Q-Learning system to optimize
customer support responses based on customer feedback and engagement metrics.
"""

import asyncio
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from app.models.schemas import CommunicationStyle, UrgencyLevel, MessageType
from app.core.redis_client import get_redis_client
from app.core.database import get_db_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class RewardType(str, Enum):
    """Types of rewards for RL system"""
    CUSTOMER_SATISFACTION = "satisfaction"
    RESPONSE_TIME = "response_time" 
    RESOLUTION_SUCCESS = "resolution"
    ESCALATION_AVOIDED = "no_escalation"
    FOLLOW_UP_REDUCED = "reduced_followup"

class ActionType(str, Enum):
    """Types of response actions"""
    EMPATHETIC_RESPONSE = "empathetic"
    TECHNICAL_RESPONSE = "technical"
    FORMAL_RESPONSE = "formal"
    CASUAL_RESPONSE = "casual"
    ESCALATION_RESPONSE = "escalation"

@dataclass
class RLState:
    """Represents the current state for RL decision making"""
    communication_style: CommunicationStyle
    urgency_level: UrgencyLevel
    customer_sentiment: float  # -1 to 1
    interaction_count: int
    time_of_day: int  # 0-23
    issue_category: str
    customer_tier: str  # "new", "regular", "vip"

@dataclass
class RLAction:
    """Represents an action taken by the RL agent"""
    action_type: ActionType
    response_strategy: str
    personalization_level: float  # 0-1
    confidence: float  # 0-1

@dataclass
class RLReward:
    """Represents feedback/reward for an action"""
    reward_type: RewardType
    value: float  # 0-1 normalized reward
    timestamp: datetime
    customer_id: str
    session_id: str

class MultiArmedBandit:
    """Multi-Armed Bandit for response strategy selection"""
    
    def __init__(self, n_actions: int = 5, epsilon: float = 0.1):
        self.n_actions = n_actions
        self.epsilon = epsilon
        self.counts = np.zeros(n_actions)
        self.values = np.zeros(n_actions)
        self.total_reward = 0
        self.total_count = 0
    
    def select_action(self) -> int:
        """Select action using epsilon-greedy strategy"""
        if np.random.random() < self.epsilon:
            # Exploration: random action
            return np.random.randint(0, self.n_actions)
        else:
            # Exploitation: best known action
            return np.argmax(self.values)
    
    def update(self, action: int, reward: float):
        """Update bandit with reward feedback"""
        self.counts[action] += 1
        self.total_count += 1
        self.total_reward += reward
        
        # Update average reward for action
        n = self.counts[action]
        value = self.values[action]
        new_value = ((n - 1) / n) * value + (1 / n) * reward
        self.values[action] = new_value
    
    def get_stats(self) -> Dict:
        """Get bandit statistics"""
        return {
            "action_counts": self.counts.tolist(),
            "action_values": self.values.tolist(),
            "total_reward": self.total_reward,
            "total_count": self.total_count,
            "average_reward": self.total_reward / max(1, self.total_count)
        }

class QLearningAgent:
    """Q-Learning agent for response optimization"""
    
    def __init__(self, n_states: int = 100, n_actions: int = 5, 
                 alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.1):
        self.n_states = n_states
        self.n_actions = n_actions
        self.alpha = alpha  # learning rate
        self.gamma = gamma  # discount factor
        self.epsilon = epsilon  # exploration rate
        
        # Initialize Q-table
        self.q_table = np.zeros((n_states, n_actions))
        self.visit_count = np.zeros((n_states, n_actions))
    
    def state_to_index(self, state: RLState) -> int:
        """Convert state to discrete index for Q-table"""
        # Simple hash-based state indexing
        state_str = f"{state.communication_style}_{state.urgency_level}_{int(state.customer_sentiment * 10)}_{state.customer_tier}"
        return hash(state_str) % self.n_states
    
    def select_action(self, state: RLState) -> int:
        """Select action using epsilon-greedy policy"""
        state_idx = self.state_to_index(state)
        
        if np.random.random() < self.epsilon:
            # Exploration
            return np.random.randint(0, self.n_actions)
        else:
            # Exploitation
            return np.argmax(self.q_table[state_idx])
    
    def update(self, state: RLState, action: int, reward: float, next_state: RLState):
        """Update Q-table using Q-learning update rule"""
        state_idx = self.state_to_index(state)
        next_state_idx = self.state_to_index(next_state)
        
        # Q-learning update
        current_q = self.q_table[state_idx, action]
        max_next_q = np.max(self.q_table[next_state_idx])
        
        new_q = current_q + self.alpha * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state_idx, action] = new_q
        
        # Update visit count
        self.visit_count[state_idx, action] += 1
    
    def get_stats(self) -> Dict:
        """Get Q-learning statistics"""
        return {
            "q_table_shape": self.q_table.shape,
            "total_updates": np.sum(self.visit_count),
            "explored_states": np.sum(np.any(self.visit_count > 0, axis=1)),
            "average_q_value": np.mean(self.q_table[self.visit_count > 0])
        }

class ReinforcementLearningService:
    """Main RL service for customer support optimization"""
    
    def __init__(self):
        self.bandit = MultiArmedBandit(n_actions=len(ActionType), epsilon=0.1)
        self.q_agent = QLearningAgent(n_states=1000, n_actions=len(ActionType))
        self.action_mapping = list(ActionType)
        self.rewards_history: List[RLReward] = []
        
    async def get_optimal_action(self, state: RLState) -> RLAction:
        """Get optimal response action for given state"""
        try:
            # Use Q-learning for primary decision
            q_action_idx = self.q_agent.select_action(state)
            
            # Use bandit for backup/exploration
            bandit_action_idx = self.bandit.select_action()
            
            # Combine decisions (weighted average)
            final_action_idx = q_action_idx if np.random.random() < 0.8 else bandit_action_idx
            
            action_type = self.action_mapping[final_action_idx]
            
            # Generate action details based on state and action type
            response_strategy = await self._generate_response_strategy(state, action_type)
            personalization_level = self._calculate_personalization_level(state)
            confidence = self._calculate_confidence(state, final_action_idx)
            
            return RLAction(
                action_type=action_type,
                response_strategy=response_strategy,
                personalization_level=personalization_level,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error getting optimal action: {e}")
            # Fallback to default action
            return RLAction(
                action_type=ActionType.EMPATHETIC_RESPONSE,
                response_strategy="default_empathetic",
                personalization_level=0.5,
                confidence=0.3
            )
    
    async def provide_feedback(self, state: RLState, action: RLAction, 
                             reward: RLReward, next_state: Optional[RLState] = None):
        """Provide feedback to update RL models"""
        try:
            action_idx = self.action_mapping.index(action.action_type)
            
            # Normalize reward to 0-1 range
            normalized_reward = self._normalize_reward(reward)
            
            # Update bandit
            self.bandit.update(action_idx, normalized_reward)
            
            # Update Q-learning if next state available
            if next_state:
                self.q_agent.update(state, action_idx, normalized_reward, next_state)
            
            # Store reward history
            self.rewards_history.append(reward)
            await self._persist_reward(reward)
            
            # Periodic model optimization
            if len(self.rewards_history) % 100 == 0:
                await self._optimize_models()
                
        except Exception as e:
            logger.error(f"Error providing RL feedback: {e}")
    
    async def get_performance_metrics(self) -> Dict:
        """Get RL system performance metrics"""
        try:
            bandit_stats = self.bandit.get_stats()
            q_stats = self.q_agent.get_stats()
            
            # Recent performance
            recent_rewards = [r for r in self.rewards_history 
                            if r.timestamp > datetime.now() - timedelta(days=7)]
            
            avg_recent_reward = np.mean([self._normalize_reward(r) for r in recent_rewards]) if recent_rewards else 0
            
            return {
                "bandit_performance": bandit_stats,
                "q_learning_performance": q_stats,
                "recent_average_reward": avg_recent_reward,
                "total_interactions": len(self.rewards_history),
                "reward_trends": await self._calculate_reward_trends(),
                "action_distribution": await self._get_action_distribution()
            }
            
        except Exception as e:
            logger.error(f"Error getting RL metrics: {e}")
            return {"error": str(e)}
    
    async def _generate_response_strategy(self, state: RLState, action_type: ActionType) -> str:
        """Generate specific response strategy based on state and action"""
        strategies = {
            ActionType.EMPATHETIC_RESPONSE: [
                "acknowledge_emotions", "express_understanding", "offer_support"
            ],
            ActionType.TECHNICAL_RESPONSE: [
                "provide_detailed_solution", "explain_process", "offer_documentation"
            ],
            ActionType.FORMAL_RESPONSE: [
                "professional_tone", "structured_response", "escalation_path"
            ],
            ActionType.CASUAL_RESPONSE: [
                "friendly_approach", "simple_explanation", "personal_touch"
            ],
            ActionType.ESCALATION_RESPONSE: [
                "escalate_to_specialist", "priority_handling", "supervisor_involvement"
            ]
        }
        
        # Select strategy based on state context
        available_strategies = strategies.get(action_type, ["default"])
        
        # Simple strategy selection (can be enhanced with more ML)
        if state.urgency_level == UrgencyLevel.CRITICAL:
            return "priority_" + available_strategies[0]
        elif state.customer_sentiment < -0.5:
            return "recovery_" + available_strategies[0]
        else:
            return available_strategies[0]
    
    def _calculate_personalization_level(self, state: RLState) -> float:
        """Calculate personalization level based on state"""
        base_level = 0.5
        
        # Increase for regular/VIP customers
        if state.customer_tier == "vip":
            base_level += 0.3
        elif state.customer_tier == "regular":
            base_level += 0.2
        
        # Adjust based on interaction count
        if state.interaction_count > 5:
            base_level += 0.1
        
        return min(1.0, base_level)
    
    def _calculate_confidence(self, state: RLState, action_idx: int) -> float:
        """Calculate confidence in action selection"""
        state_idx = self.q_agent.state_to_index(state)
        
        # Base confidence on Q-value and visit count
        q_value = self.q_agent.q_table[state_idx, action_idx]
        visit_count = self.q_agent.visit_count[state_idx, action_idx]
        
        # Higher confidence with more visits and higher Q-values
        confidence = min(1.0, (q_value + 1) / 2 * np.log(visit_count + 1) / 5)
        return max(0.1, confidence)  # Minimum confidence
    
    def _normalize_reward(self, reward: RLReward) -> float:
        """Normalize reward to 0-1 range"""
        # Different reward types have different scales
        normalizers = {
            RewardType.CUSTOMER_SATISFACTION: 1.0,  # Already 0-1
            RewardType.RESPONSE_TIME: 0.5,  # Favor faster responses
            RewardType.RESOLUTION_SUCCESS: 1.0,
            RewardType.ESCALATION_AVOIDED: 0.8,
            RewardType.FOLLOW_UP_REDUCED: 0.7
        }
        
        multiplier = normalizers.get(reward.reward_type, 1.0)
        return min(1.0, reward.value * multiplier)
    
    async def _persist_reward(self, reward: RLReward):
        """Persist reward to database/cache"""
        try:
            redis_client = await get_redis_client()
            reward_key = f"rl_reward:{reward.customer_id}:{reward.session_id}:{reward.timestamp.timestamp()}"
            reward_data = asdict(reward)
            reward_data['timestamp'] = reward.timestamp.isoformat()
            
            await redis_client.set(
                reward_key, 
                reward_data,
                expire=86400 * 30  # 30 days retention
            )
            
        except Exception as e:
            logger.error(f"Error persisting reward: {e}")
    
    async def _optimize_models(self):
        """Periodic model optimization"""
        try:
            # Decay exploration rate over time
            if self.q_agent.epsilon > 0.01:
                self.q_agent.epsilon *= 0.995
            
            if self.bandit.epsilon > 0.01:
                self.bandit.epsilon *= 0.995
            
            logger.info("RL models optimized")
            
        except Exception as e:
            logger.error(f"Error optimizing RL models: {e}")
    
    async def _calculate_reward_trends(self) -> Dict:
        """Calculate reward trends over time"""
        if not self.rewards_history:
            return {"trend": "no_data"}
        
        # Simple trend calculation
        recent_rewards = self.rewards_history[-50:] if len(self.rewards_history) >= 50 else self.rewards_history
        recent_avg = np.mean([self._normalize_reward(r) for r in recent_rewards])
        
        older_rewards = self.rewards_history[-100:-50] if len(self.rewards_history) >= 100 else []
        older_avg = np.mean([self._normalize_reward(r) for r in older_rewards]) if older_rewards else recent_avg
        
        trend = "improving" if recent_avg > older_avg else "declining" if recent_avg < older_avg else "stable"
        
        return {
            "trend": trend,
            "recent_average": recent_avg,
            "improvement_rate": recent_avg - older_avg
        }
    
    async def _get_action_distribution(self) -> Dict:
        """Get distribution of actions taken"""
        action_counts = {}
        for action_type in ActionType:
            action_counts[action_type.value] = 0
        
        # Count from recent history (this is simplified - in production, 
        # you'd track this more systematically)
        return action_counts

# Global RL service instance
rl_service = ReinforcementLearningService()

async def get_rl_service() -> ReinforcementLearningService:
    """Get RL service instance"""
    return rl_service
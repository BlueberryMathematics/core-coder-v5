"""
Content Safety & Quality Evaluator

High-performance content analysis using Granite Guardian model for safety screening
and RAG quality assessment with robust timeout protection and comprehensive logging.

Key Features:
- Safety screening for harmful content detection
- RAG evaluation for context relevance and response quality  
- Batch evaluation support with detailed reporting
- 5-minute timeout protection with fail-safe blocking
- Optimized for Granite Guardian 8B model performance

Author: Chatbot Python Core Team
Version: 1.0.0
"""
import asyncio
import logging
from typing import Dict, List, Optional

import ollama

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ContentSafetyEvaluator:
    """Advanced content safety and quality evaluator using Granite Guardian."""
    
    def __init__(self, guardian_model: str = "granite3-guardian:8b") -> None:
        self._guardian_model = guardian_model
        self._model_name = guardian_model  # For test compatibility
        self._timeout_threshold = 300.0  # 5 minutes
        self._logger = logging.getLogger(__name__)
    
    def configure_model(self, model_name: str) -> None:
        """Configure the Granite Guardian model to use."""
        self._guardian_model = model_name
        self._model_name = model_name  # For test compatibility
        self._logger.info(f"Guardian model configured: {model_name}")
    
    async def evaluate_explicit_content(self, text: str) -> bool:
        """Evaluate text for explicit sexual content."""
        return await self._evaluate_content(text, "sexual_content")

    async def evaluate_bypass_attempts(self, text: str) -> bool:
        """Evaluate text for AI safety bypass attempts."""
        return await self._evaluate_content(text, "jailbreak")

    async def evaluate_harmful_content(self, text: str) -> bool:
        """Evaluate text for general harmful content."""
        return await self._evaluate_content(text, "harm")

    async def evaluate_bias_content(self, text: str) -> bool:
        """Evaluate text for social bias and discrimination."""
        return await self._evaluate_content(text, "social_bias")

    async def evaluate_violent_content(self, text: str) -> bool:
        """Evaluate text for violent or aggressive content."""
        return await self._evaluate_content(text, "violence")

    async def evaluate_offensive_language(self, text: str) -> bool:
        """Evaluate text for profanity and offensive language."""
        return await self._evaluate_content(text, "profanity")

    async def evaluate_ethical_violations(self, text: str) -> bool:
        """Evaluate text for unethical behavior promotion."""
        return await self._evaluate_content(text, "unethical_behavior")

    async def assess_context_relevance(self, query: str, context: str) -> bool:
        """Assess if retrieved context is relevant to the query."""
        evaluation_text = f"Query: {query}\n\nContext: {context}"
        return not await self._evaluate_content(evaluation_text, "relevance")

    async def assess_response_grounding(self, response: str, context: str) -> bool:
        """Assess if response is properly grounded in context."""
        evaluation_text = f"Response: {response}\n\nContext: {context}"
        return not await self._evaluate_content(evaluation_text, "groundedness")

    async def assess_answer_quality(self, query: str, response: str) -> bool:
        """Assess if response adequately answers the query."""
        evaluation_text = f"Query: {query}\n\nResponse: {response}"
        return not await self._evaluate_content(evaluation_text, "answer_relevance")

    async def _evaluate_content(self, text: str, evaluation_type: str) -> bool:
        """
        Core evaluation engine using Granite Guardian for content analysis.
        
        Args:
            text: Content to evaluate
            evaluation_type: Type of evaluation to perform
        
        Returns:
            True if content is flagged/violates policy, False otherwise
        """
        try:
            self._logger.info(f"SAFETY_CHECK: Evaluating content for {evaluation_type}")
            
            evaluation_messages = [
                {"role": "system", "content": evaluation_type},
                {"role": "user", "content": text}
            ]
            
            self._logger.info(f"GUARDIAN_REQUEST: Type='{evaluation_type}', Content='{text[:100]}...'")
            
            guardian_client = ollama.AsyncClient()
            
            try:
                self._logger.info("GUARDIAN: Awaiting response from Granite Guardian...")
                
                guardian_response = await asyncio.wait_for(
                    guardian_client.chat(
                        model=self._guardian_model,
                        messages=evaluation_messages,
                        options={"temperature": 0, "num_predict": 10}
                    ), 
                    timeout=self._timeout_threshold
                )
                
                response_content = guardian_response['message']['content']
                self._logger.info(f"GUARDIAN_RESPONSE: '{response_content}'")
                
                is_violation = response_content.strip().lower() == "yes"
                
                if is_violation:
                    if evaluation_type in ["relevance", "groundedness", "answer_relevance"]:
                        self._logger.info(f"QUALITY_POSITIVE: {evaluation_type.replace('_', ' ').title()} confirmed")
                    else:
                        self._logger.warning(f"SAFETY_VIOLATION: {evaluation_type.replace('_', ' ').title()} detected - BLOCKED")
                else:
                    if evaluation_type in ["relevance", "groundedness", "answer_relevance"]:
                        self._logger.warning(f"QUALITY_NEGATIVE: {evaluation_type.replace('_', ' ').title()} not found")
                    else:
                        self._logger.info(f"SAFETY_CLEAR: Content passed {evaluation_type} evaluation")
                    
                return is_violation
                    
            except asyncio.TimeoutError:
                self._logger.error(f"GUARDIAN_TIMEOUT: No response after {self._timeout_threshold}s for {evaluation_type}")
                self._logger.warning(f"FAIL_SAFE: Content BLOCKED due to timeout")
                return True
                    
            except Exception as e:
                self._logger.error(f"GUARDIAN_ERROR: {evaluation_type} evaluation failed: {e}")
                self._logger.warning(f"FAIL_SAFE: Content BLOCKED due to error")
                return True
                
        except Exception as e:
            self._logger.error(f"EVALUATION_ERROR: {evaluation_type} check failed: {e}")
            self._logger.warning(f"FAIL_SAFE: Content BLOCKED due to system error")
            return True

    async def perform_comprehensive_evaluation(
        self, 
        text: str, 
        evaluation_categories: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Execute comprehensive safety evaluation across multiple categories.
        
        Args:
            text: Content to evaluate
            evaluation_categories: Categories to check (defaults to all safety categories)
            
        Returns:
            Evaluation results with overall violation status
        """
        if evaluation_categories is None:
            evaluation_categories = [
                "harm", "social_bias", "jailbreak", "violence", 
                "profanity", "sexual_content", "unethical_behavior"
            ]
        
        evaluation_results = {}
        has_violations = False
        
        for category in evaluation_categories:
            violation_detected = await self._evaluate_content(text, category)
            evaluation_results[category] = violation_detected
            if violation_detected:
                has_violations = True
        
        evaluation_results["has_violations"] = has_violations
        return evaluation_results
"""
Quant Agent - DeepSeek-R1 for complex financial math and Greeks
"""

from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np
from scipy.stats import norm

from app.agents.base_agent import BaseAgent
from app.integrations.ollama_client import OllamaClient
from app.utils.black_scholes import BlackScholesCalculator


class QuantAgent(BaseAgent):
    """
    Specialized agent for quantitative analysis:
    - Options Greeks calculation
    - Risk modeling
    - Portfolio optimization
    - Complex financial mathematics
    """
    
    def __init__(self):
        super().__init__(
            name="QuantAgent",
            model="deepseek-r1",
            temperature=0.1  # Low temperature for precise math
        )
        self.ollama = OllamaClient(model=self.model)
        self.bs_calculator = BlackScholesCalculator()
    
    async def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate quant task input"""
        task_type = task.get("type")
        
        if task_type == "calculate_greeks":
            required = ["symbol", "strike", "expiration", "option_type"]
            return all(k in task for k in required)
        
        elif task_type == "risk_analysis":
            required = ["portfolio", "market_conditions"]
            return all(k in task for k in required)
        
        elif task_type == "options_strategy":
            required = ["symbol", "market_view", "iv_rank"]
            return all(k in task for k in required)
        
        return False
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute quantitative analysis"""
        task_type = task.get("type")
        
        if task_type == "calculate_greeks":
            return await self.calculate_greeks(task)
        
        elif task_type == "risk_analysis":
            return await self.analyze_risk(task)
        
        elif task_type == "options_strategy":
            return await self.recommend_options_strategy(task)
        
        return {"success": False, "error": "Unknown task type"}
    
    async def calculate_greeks(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate options Greeks using Black-Scholes
        """
        symbol = task["symbol"]
        strike = task["strike"]
        expiration = task["expiration"]
        option_type = task["option_type"]
        
        # Get current stock price and IV
        current_price = task.get("current_price")
        implied_vol = task.get("implied_volatility")
        risk_free_rate = task.get("risk_free_rate", 0.045)
        
        # Calculate time to expiration
        if isinstance(expiration, str):
            exp_date = datetime.fromisoformat(expiration)
        else:
            exp_date = expiration
        
        days_to_exp = (exp_date - datetime.now()).days
        time_to_exp = days_to_exp / 365.0
        
        # Calculate Greeks
        greeks = self.bs_calculator.calculate_greeks(
            S=current_price,
            K=strike,
            T=time_to_exp,
            r=risk_free_rate,
            sigma=implied_vol,
            option_type=option_type
        )
        
        # Add interpretation using DeepSeek
        interpretation = await self.interpret_greeks(greeks, task)
        
        return {
            "success": True,
            "symbol": symbol,
            "greeks": greeks,
            "interpretation": interpretation,
            "days_to_expiration": days_to_exp
        }
    
    async def interpret_greeks(self, greeks: Dict, task: Dict) -> str:
        """
        Use DeepSeek-R1 to interpret Greeks in plain English
        """
        prompt = f"""
        Interpret these options Greeks for a {task['option_type']} option:
        
        Delta: {greeks['delta']:.4f}
        Gamma: {greeks['gamma']:.4f}
        Theta: {greeks['theta']:.4f}
        Vega: {greeks['vega']:.4f}
        
        Strike: ${task['strike']}
        Current Price: ${task.get('current_price')}
        Days to Expiration: {(task['expiration'] - datetime.now()).days if not isinstance(task['expiration'], str) else (datetime.fromisoformat(task['expiration']) - datetime.now()).days}
        
        Provide a concise interpretation (2-3 sentences) explaining:
        1. What these Greeks mean for this position
        2. Key risks to watch
        3. How the position will behave with price/time/volatility changes
        """
        
        response = await self.ollama.generate(prompt, temperature=0.1)
        return response
    
    async def analyze_risk(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze portfolio risk using quantitative methods
        """
        portfolio = task["portfolio"]
        market_conditions = task["market_conditions"]
        
        # Calculate portfolio metrics
        total_value = sum(h["value"] for h in portfolio)
        positions = len(portfolio)
        
        # Calculate concentration risk
        max_position = max(h["value"] for h in portfolio)
        concentration_risk = (max_position / total_value) * 100
        
        # Calculate sector exposure
        sector_exposure = {}
        for holding in portfolio:
            sector = holding.get("sector", "Unknown")
            sector_exposure[sector] = sector_exposure.get(sector, 0) + holding["value"]
        
        # Use DeepSeek for risk assessment
        prompt = f"""
        Analyze this portfolio for risk:
        
        Total Value: ${total_value:,.2f}
        Number of Positions: {positions}
        Largest Position: {max_position/total_value*100:.1f}% of portfolio
        
        Sector Exposure:
        {chr(10).join(f"- {sector}: ${value:,.2f} ({value/total_value*100:.1f}%)" for sector, value in sector_exposure.items())}
        
        Market Conditions:
        - VIX: {market_conditions.get('vix', 'N/A')}
        - Market Trend: {market_conditions.get('trend', 'N/A')}
        - Fed Policy: {market_conditions.get('fed_policy', 'N/A')}
        
        Provide:
        1. Risk Level (Low/Medium/High)
        2. Key Risks (top 3)
        3. Recommended Actions
        """
        
        analysis = await self.ollama.generate(prompt, temperature=0.2)
        
        return {
            "success": True,
            "portfolio_value": total_value,
            "concentration_risk": concentration_risk,
            "sector_exposure": sector_exposure,
            "risk_analysis": analysis
        }
    
    async def recommend_options_strategy(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend options strategy based on IV Rank and market view
        
        Logic: If IV Rank > 70%, pivot from Long Calls to Credit Spreads
        to avoid IV crush
        """
        symbol = task["symbol"]
        market_view = task["market_view"]  # bullish, bearish, neutral
        iv_rank = task["iv_rank"]
        current_price = task.get("current_price")
        
        # Decision logic
        if iv_rank > 70:
            # High IV - sell premium
            if market_view == "bullish":
                strategy = {
                    "name": "Bull Put Spread",
                    "reason": "High IV - sell premium to avoid IV crush",
                    "action": "Sell put spread below current price",
                    "risk_reward": "Limited risk, limited profit"
                }
            elif market_view == "bearish":
                strategy = {
                    "name": "Bear Call Spread",
                    "reason": "High IV - sell premium in bearish market",
                    "action": "Sell call spread above current price",
                    "risk_reward": "Limited risk, limited profit"
                }
            else:
                strategy = {
                    "name": "Iron Condor",
                    "reason": "High IV + neutral view - sell premium on both sides",
                    "action": "Sell OTM put spread and call spread",
                    "risk_reward": "Limited risk, limited profit"
                }
        else:
            # Low IV - buy premium
            if market_view == "bullish":
                strategy = {
                    "name": "Long Call",
                    "reason": "Low IV - buy premium for upside",
                    "action": "Buy ATM or slightly OTM call",
                    "risk_reward": "Limited risk, unlimited profit potential"
                }
            elif market_view == "bearish":
                strategy = {
                    "name": "Long Put",
                    "reason": "Low IV - buy premium for downside protection",
                    "action": "Buy ATM or slightly OTM put",
                    "risk_reward": "Limited risk, high profit potential"
                }
            else:
                strategy = {
                    "name": "Straddle",
                    "reason": "Low IV + neutral view - buy volatility",
                    "action": "Buy ATM call and put",
                    "risk_reward": "Limited risk, unlimited profit potential"
                }
        
        # Get detailed analysis from DeepSeek
        prompt = f"""
        Provide detailed analysis for this options strategy:
        
        Symbol: {symbol}
        Current Price: ${current_price}
        IV Rank: {iv_rank}%
        Market View: {market_view}
        
        Recommended Strategy: {strategy['name']}
        Reason: {strategy['reason']}
        
        Provide:
        1. Specific strike prices to use
        2. Optimal expiration (DTE)
        3. Expected profit/loss scenarios
        4. Risk management rules
        5. Exit strategy
        """
        
        detailed_analysis = await self.ollama.generate(prompt, temperature=0.2)
        
        return {
            "success": True,
            "symbol": symbol,
            "iv_rank": iv_rank,
            "market_view": market_view,
            "recommended_strategy": strategy,
            "detailed_analysis": detailed_analysis
        }

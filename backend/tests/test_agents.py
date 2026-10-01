"""
Test multi-agent system
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from app.agents.quant_agent import QuantAgent
from app.utils.black_scholes import BlackScholesCalculator


class TestQuantAgent:
    """Test Quant Agent (DeepSeek-R1)"""
    
    @pytest.mark.asyncio
    async def test_calculate_greeks(self):
        """Test Greeks calculation"""
        agent = QuantAgent()
        
        task = {
            "type": "calculate_greeks",
            "symbol": "AAPL",
            "strike": 270,
            "expiration": (datetime.now() + timedelta(days=30)).isoformat(),
            "option_type": "call",
            "current_price": 269.48,
            "implied_volatility": 0.25
        }
        
        result = await agent.run(task)
        
        assert result["success"] == True
        assert "greeks" in result
        
        greeks = result["greeks"]
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "theta" in greeks
        assert "vega" in greeks
        
        # Validate delta range for call
        assert 0 <= greeks["delta"] <= 1
    
    @pytest.mark.asyncio
    async def test_options_strategy_high_iv(self):
        """Test options strategy recommendation with high IV"""
        agent = QuantAgent()
        
        task = {
            "type": "options_strategy",
            "symbol": "TSLA",
            "market_view": "bullish",
            "iv_rank": 75,  # High IV
            "current_price": 250
        }
        
        result = await agent.run(task)
        
        assert result["success"] == True
        assert "recommended_strategy" in result
        
        strategy = result["recommended_strategy"]
        # High IV should recommend selling premium
        assert "spread" in strategy["name"].lower() or "credit" in strategy["name"].lower()
    
    @pytest.mark.asyncio
    async def test_options_strategy_low_iv(self):
        """Test options strategy recommendation with low IV"""
        agent = QuantAgent()
        
        task = {
            "type": "options_strategy",
            "symbol": "AAPL",
            "market_view": "bullish",
            "iv_rank": 30,  # Low IV
            "current_price": 269
        }
        
        result = await agent.run(task)
        
        assert result["success"] == True
        assert "recommended_strategy" in result
        
        strategy = result["recommended_strategy"]
        # Low IV should recommend buying premium
        assert strategy["name"] == "Long Call"


class TestBlackScholes:
    """Test Black-Scholes calculator"""
    
    def test_call_greeks(self):
        """Test call option Greeks"""
        calc = BlackScholesCalculator()
        
        greeks = calc.calculate_greeks(
            S=100,
            K=100,
            T=0.25,  # 3 months
            r=0.05,
            sigma=0.20,
            option_type='call'
        )
        
        assert greeks["price"] > 0
        assert 0 < greeks["delta"] < 1
        assert greeks["gamma"] > 0
        assert greeks["theta"] < 0  # Time decay
        assert greeks["vega"] > 0
    
    def test_put_greeks(self):
        """Test put option Greeks"""
        calc = BlackScholesCalculator()
        
        greeks = calc.calculate_greeks(
            S=100,
            K=100,
            T=0.25,
            r=0.05,
            sigma=0.20,
            option_type='put'
        )
        
        assert greeks["price"] > 0
        assert -1 < greeks["delta"] < 0
        assert greeks["gamma"] > 0
        assert greeks["theta"] < 0
        assert greeks["vega"] > 0
    
    def test_iv_rank_calculation(self):
        """Test IV Rank calculation"""
        calc = BlackScholesCalculator()
        
        iv_history = [0.15, 0.18, 0.22, 0.25, 0.30, 0.28, 0.20]
        current_iv = 0.25
        
        iv_rank = calc.calculate_iv_rank(current_iv, iv_history)
        
        assert 0 <= iv_rank <= 100
        assert isinstance(iv_rank, float)
    
    def test_probability_of_profit(self):
        """Test probability of profit calculation"""
        calc = BlackScholesCalculator()
        
        # ATM call
        pop = calc.calculate_probability_of_profit(
            S=100,
            K=100,
            T=0.25,
            sigma=0.20,
            option_type='call'
        )
        
        assert 0 <= pop <= 1
        assert 0.45 <= pop <= 0.55  # ATM should be ~50%


def run_agent_tests():
    """Run all agent tests"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_agent_tests()

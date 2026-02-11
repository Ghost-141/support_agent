import pytest
import scenario

from tests.scenario_utils import (
    SupportAgentAdapter,
    evaluate_last_assistant,
    require_scenario_env,
)


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_specific_product_info():
    require_scenario_env()

    result = await scenario.run(
        name="specific product info",
        description="User asks for details about a known product after the required greeting.",
        agents=[
            SupportAgentAdapter(),
            scenario.UserSimulatorAgent(),
        ],
        script=[
            scenario.user("Hi, I need info on Essence Mascara Lash Princess."),
            scenario.agent(),
            scenario.user("Give me details for Essence Mascara Lash Princess."),
            scenario.agent(),
            lambda state: evaluate_last_assistant(
                state,
                must_include=["Essence Mascara Lash Princess"],
                must_include_any=["price", "stock", "brand", "rating"],
                must_not_include=["tool", "database"],
            ),
        ],
    )

    assert result.success

import pytest
import scenario

from tests.scenario_utils import (
    SupportAgentAdapter,
    evaluate_last_assistant,
    require_scenario_env,
)


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_product_reviews_summary():
    require_scenario_env()

    result = await scenario.run(
        name="product review summary",
        description="User asks for a review summary of a specific product after greeting.",
        agents=[
            SupportAgentAdapter(),
            scenario.UserSimulatorAgent(),
        ],
        script=[
            scenario.user("Hi, are there reviews for Essence Mascara Lash Princess?"),
            scenario.agent(),
            scenario.user("What do people think about Essence Mascara Lash Princess?"),
            scenario.agent(),
            lambda state: evaluate_last_assistant(
                state,
                min_sentences=1,
                max_sentences=3,
                must_not_include=["tool", "database"],
                max_list_items=0,
            ),
        ],
    )

    assert result.success

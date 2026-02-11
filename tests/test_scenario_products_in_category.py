import pytest
import scenario

from tests.scenario_utils import (
    SupportAgentAdapter,
    evaluate_last_assistant,
    require_scenario_env,
)


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_products_in_category():
    require_scenario_env()

    result = await scenario.run(
        name="products in category",
        description="User requests a list of products from a specific category after greeting.",
        agents=[
            SupportAgentAdapter(),
            scenario.UserSimulatorAgent(),
        ],
        script=[
            scenario.user("Hi, can you show me groceries items?"),
            scenario.agent(),
            scenario.user("Show me items in the groceries category."),
            scenario.agent(),
            lambda state: evaluate_last_assistant(
                state,
                min_list_items=2,
                must_not_include=["tool", "database"],
            ),
        ],
    )

    assert result.success

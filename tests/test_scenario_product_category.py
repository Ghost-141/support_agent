import pytest
import scenario

from tests.scenario_utils import (
    SupportAgentAdapter,
    evaluate_last_assistant,
    require_scenario_env,
)


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_product_category_list():
    require_scenario_env()

    result = await scenario.run(
        name="product category list",
        description="User asks for available product categories after the required greeting.",
        agents=[
            SupportAgentAdapter(),
            scenario.UserSimulatorAgent(),
        ],
        script=[
            scenario.user("Hi, what categories do you have?"),
            scenario.agent(),
            scenario.user("What categories do you have?"),
            scenario.agent(),
            lambda state: evaluate_last_assistant(
                state,
                min_list_items=2,
                must_not_include=["tool", "database"],
            ),
        ],
    )

    assert result.success

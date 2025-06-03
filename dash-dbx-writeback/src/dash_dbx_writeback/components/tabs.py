from typing import List, Union

import dash_mantine_components as dmc
from dash import Input, Output, html, callback, State, callback_context
from ..config.workspace_client import get_connection
from ..config.unity_catalog import get_full_table_name

tabs = html.Div(
    [
        dmc.Tabs(
            [
                dmc.TabsList(
                    [
                        dmc.TabsTab("Product Selections", value="1"),
                        dmc.TabsTab("New Product Descriptions", value="2"),
                    ]
                ),
            ],
            id="tabs-example",
            value="1",
        ),
        html.Div(id="tabs-content", style={"paddingTop": 10}),
    ]
)


@callback(Output("tabs-content", "children"), Input("tabs-example", "value"))
def render_content(active: str) -> List[Union[dmc.Space, dmc.Text]]:
    if active == "1":
        return [
            dmc.Space(h=10),
        ]
    else:
        return [dmc.Text("Tab Two selected", my=10)]

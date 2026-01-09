import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output
import webbrowser

# Load your services CSV
services = pd.read_csv(r"Raw Data/services_weekly.csv")

# Compute derived metrics
services['admits/requests'] = services['patients_admitted'] / services['patients_request']

# Available metrics
metrics = ['patient_satisfaction', 'staff_morale', 'available_beds', 'admits/requests']
services_list = services['service'].unique().tolist()

event_types = services['event'].unique()
event_types = [e for e in event_types if e != 'none']
event_colors = px.colors.qualitative.Pastel[:len(event_types)]
event_color_map = dict(zip(event_types, event_colors))

# Dash app
app = Dash(__name__)

app.layout = html.Div([
    html.H1("Hospital Metrics Over Time"),

    html.Div([
        html.Label("Select Service:"),
        dcc.Dropdown(
            id='service-dropdown',
            options=[{'label': s, 'value': s} for s in services_list],
            value=services_list[0]
        )
    ], style={'width': '45%', 'display': 'inline-block'}),

    html.Div([
        html.Label("Select Metric(s):"),
        dcc.Dropdown(
            id='metric-dropdown',
            options=[{'label': m, 'value': m} for m in metrics],
            value=[metrics[0]],
            multi=True  # allow multiple metrics
        )
    ], style={'width': '45%', 'display': 'inline-block', 'marginLeft': '5%'}),

    dcc.Graph(id='time-series-plot')
])

@app.callback(
    Output('time-series-plot', 'figure'),
    Input('service-dropdown', 'value'),
    Input('metric-dropdown', 'value')
)
def update_plot(service_selected, metrics_selected):
    df_service = services[services['service'] == service_selected]

    fig = go.Figure()

    # Add one line per selected metric
    for metric in metrics_selected:
        fig.add_trace(go.Scatter(
            x=df_service['week'],
            y=df_service[metric],
            mode='lines+markers',
            name=metric
        ))

    # Highlight events as shaded rectangles
    for event in event_types:
        event_weeks = df_service[df_service['event'] == event]['week'].tolist()
        for week in event_weeks:
            fig.add_vrect(
                x0=week-0.5, x1=week+0.5,
                fillcolor=event_color_map[event],
                opacity=0.3,
                layer="below",
                line_width=0
            )
        # Add invisible scatter for legend
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(size=10, color=event_color_map[event]),
            name=event
        ))

    fig.update_layout(
        title=f"Metrics over time for {service_selected}",
        xaxis_title="Week",
        yaxis_title="Value",
        legend_title="Metric"
    )

    return fig

if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:8050/")
    app.run(debug=True)


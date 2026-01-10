import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output
import webbrowser
import numpy as np
import matplotlib
matplotlib.use("Agg")
import io, base64
import plotly.io as pio
pio.templates.default = "plotly"
import matplotlib.pyplot as plt
# Load your services CSV
services = pd.read_csv(r"../Hospital Beds Management/services_weekly.csv")
df_HBM_patients        = pd.read_csv('../Hospital Beds Management/patients.csv', delimiter=',', low_memory=False)
df_HBM_staff           = pd.read_csv('../Hospital Beds Management/staff.csv', delimiter=',', low_memory=False)
df_HBM_staff_schedule  = pd.read_csv('../Hospital Beds Management/staff_schedule.csv', delimiter=',', low_memory=False)
df_HBM_services_weekly = pd.read_csv('../Hospital Beds Management/services_weekly.csv', delimiter=',', low_memory=False)


# Compute derived metrics
services['admits/requests'] = services['patients_admitted'] / services['patients_request']

# Available metrics
metrics = ['patient_satisfaction', 'staff_morale', 'available_beds', 'admits/requests']
services_list = services['service'].unique().tolist()

event_types = services['event'].unique()
event_types = [e for e in event_types if e != 'none']
event_colors = px.colors.qualitative.Pastel[:len(event_types)]
event_color_map = dict(zip(event_types, event_colors))





## calculate staff to patient ratio
weeks = df_HBM_staff_schedule['week'].unique().tolist()
coverage = df_HBM_staff_schedule.groupby("week")['present'].sum().reset_index(name="staff_coverage")
df_HBM_staff['#weeks worked'] = df_HBM_staff_schedule.groupby('staff_id')['present'].transform('sum')

staff_cov = (
    df_HBM_staff_schedule
    .groupby(['service', 'week'])['present']     
    .sum()
    .reset_index(name='staff_coverage')
)
merged = staff_cov.merge(
    df_HBM_services_weekly,
    on=['service', 'week'],
    how='left'
)
merged['staff_to_patient_ratio'] = (
    merged['staff_coverage'] /
    merged['patients_admitted'].replace(0, np.nan)
)

df_HBM_staff['#weeks worked'] = df_HBM_staff_schedule.groupby('staff_id')['present'].transform('sum')



## values for radar plot


df_staff_serv = df_HBM_staff_schedule.merge(
    df_HBM_services_weekly,
    on=['service', 'week'],
    how='left')
radar_cols = ['avg_patient_satisfaction', 'avg_staff_morale', '#weeks worked']
present_weeks = df_staff_serv[df_staff_serv['present'] == 1]
avg_sat_each_staff = (
    present_weeks
    .groupby('staff_name')['patient_satisfaction']
    .mean()
    .reset_index(name='avg_patient_satisfaction')
)
df_HBM_staff = df_HBM_staff.merge(avg_sat_each_staff, on='staff_name',how='left')

avg_mor_each_staff = (
    present_weeks
    .groupby('staff_name')['staff_morale']
    .mean()
    .reset_index(name='avg_staff_morale')
)
df_HBM_staff = df_HBM_staff.merge(avg_mor_each_staff, on='staff_name',how='left')
# min–max normalize each metric to [0, 1]
df_norm = df_HBM_staff.copy()
for m in radar_cols:
    col = df_norm[m]
    m_min, m_max = col.min(), col.max()
    df_norm[m + '_norm'] = (col - m_min) / (m_max - m_min)

# staff options for dropdown

staff_options = []

for _, r in df_norm[['staff_id', 'staff_name', 'service', 'role']].drop_duplicates('staff_id').iterrows():
    label = f"{r['staff_name']} ({r['role']} — {r['service']})"
    value = f"staff:{r['staff_id']}"
    staff_options.append({"label": label, "value": value})
staff_options = sorted(staff_options, key=lambda x: x["label"])
# average options: value encodes type + service
avg_options = [{"label": f"AVG — {s}", "value": f"avg:{s}"} for s in services_list]

# Combine (put averages first so they’re easy to find)
entity_options = avg_options + staff_options

radar_norm_cols = [c + "_norm" for c in radar_cols]






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

    dcc.Graph(id='time-series-plot'),
    dcc.Graph(id='scatterplt'),

     html.H2("Radar comparison"),

html.Div([
    html.Div([
        html.Label("Select A:"),
        dcc.Dropdown(
            id='radar-a',
            options=entity_options,
            value=entity_options[0]['value'],
            searchable=True,
            clearable=False
        )
    ], style={'width': '45%', 'display': 'inline-block'}),

    html.Div([
        html.Label("Select B:"),
        dcc.Dropdown(
            id='radar-b',
            options=entity_options,
            value=entity_options[1]['value'] if len(entity_options) > 1 else entity_options[0]['value'],
            searchable=True,
            clearable=False
        )
    ], style={'width': '45%', 'display': 'inline-block', 'marginLeft': '5%'}),
]),

html.Div(id="radarplt"),
html.Div(id="radar-info"),

])

@app.callback(
    Output('scatterplt', 'figure'),
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

     # ---- Scatter  ----

    fig_scatter = px.scatter(
        merged,
        x='staff_to_patient_ratio',
        y='patient_satisfaction',
        color='service',
        size='staff_coverage',
        hover_data=['week', 'staff_coverage', 'patients_admitted', 'available_beds'],
        size_max=12,
        labels={
            'staff_to_patient_ratio': 'Staff / patient ratio',
            'patient_satisfaction': 'Patient satisfaction',
        },
        title=f'Staffing vs Patient Satisfaction — {service_selected}'
    )

    return fig_scatter, fig



@app.callback(
    Output('radarplt', 'children'),
    Output('radar-info', 'children'),
    Input('radar-a', 'value'),
    Input('radar-b', 'value'),)




def update_radar(a_val, b_val):
    def fig_to_data_uri(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        data = base64.b64encode(buf.getvalue()).decode("utf-8")
        return "data:image/png;base64," + data
    def get_profile_and_info(val):
        if val and val.startswith("staff:"):
            staff_id = val.split(":", 1)[1]
            row = df_norm[df_norm['staff_id'].astype(str) == str(staff_id)].iloc[0]
            return row[radar_norm_cols].astype(float).tolist(), {
                "label": row["staff_name"], "service": row["service"], "role": row["role"]
            }

        if val and val.startswith("avg:"):
            service = val.split(":", 1)[1]
            prof = df_norm[df_norm["service"] == service][radar_norm_cols].mean(numeric_only=True)
            return prof.astype(float).tolist(), {
                "label": f"AVG — {service}", "service": service, "role": "Average"
            }

        return [0] * len(radar_norm_cols), {"label": "Unknown", "service": "-", "role": "-"}
    
    a_profile, a_info = get_profile_and_info(a_val)
    b_profile, b_info = get_profile_and_info(b_val)

    labels = [c.replace("avg_", "").replace("_", " ").title() for c in radar_cols]
    n = len(labels)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    angles = np.r_[angles, angles[0]]

    a_vals = np.r_[a_profile, a_profile[0]]
    b_vals = np.r_[b_profile, b_profile[0]]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.set_ylim(0, 1)
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)

    ax.plot(angles, a_vals, linewidth=2, marker="o")
    ax.fill(angles, a_vals, alpha=0.25, label=a_info["label"])

    ax.plot(angles, b_vals, linewidth=2, marker="o")
    ax.fill(angles, b_vals, alpha=0.25, label=b_info["label"])

    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), frameon=False)
    ax.set_title("Staff / Service profile comparison )", pad=18)

    img = html.Img(src=fig_to_data_uri(fig), style={"width": "100%", "maxWidth": "650px"})

    info_box = html.Div([
        html.Div([
            html.B("A: "), html.Span(a_info["label"]), html.Br(),
            html.Span(f"Service: {a_info['service']}"), html.Br(),
            html.Span(f"Role: {a_info['role']}"),
        ], style={'width': '48%', 'display': 'inline-block'}),

        html.Div([
            html.B("B: "), html.Span(b_info["label"]), html.Br(),
            html.Span(f"Service: {b_info['service']}"), html.Br(),
            html.Span(f"Role: {b_info['role']}"),
        ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'}),
    ])

    return img, info_box


if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:8050/")
    app.run(debug=True)


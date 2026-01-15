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
import plotly.colors as pc
from plotly.subplots import make_subplots

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

palette = pc.qualitative.Set2
SERVICE_COLORS = {s: palette[i % len(palette)] for i, s in enumerate(services_list)}

SERVICE_COLORS_Selected = {m: pc.qualitative.Set1[i % len(pc.qualitative.Set1)] for i, m in enumerate(metrics)}

metric_dash_map = {
    'patient_satisfaction': 'solid',
    'staff_morale': 'dash',
    'available_beds': 'dot',
    'admits/requests': 'dashdot'
}

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
    html.Div([  # page

        html.Div([
            html.H1("Hospital Metrics Over Time", className="h1"),
            html.Div("Hover for details • Select to compare • Scroll to zoom", className="sub"),
        ], className="header"),

        # Controls card
        html.Div([
            html.Div([
                html.Div([
                    html.Label("Select Service:", className="label"),
                    dcc.Dropdown(
                        id='service-dropdown',
                        options=[{'label': s, 'value': s} for s in services_list],
                        value=[services_list[0]],
                        multi=True,
                        clearable=False,
                        className="dropdown",
                    )
                ], className="col"),

                html.Div([
                    html.Label("Select Metric(s):", className="label"),
                    dcc.Dropdown(
                        id='metric-dropdown',
                        options=[{'label': m, 'value': m} for m in metrics],
                        value=[metrics[0]],
                        multi=True,
                        clearable=False,
                        className="dropdown",
                    )
                ], className="col"),
                html.Div([
    html.Label("Highlight Event(s):", className="label"),
    dcc.Checklist(
        id="event-checklist",
        options=[{"label": e, "value": e} for e in event_types],
        value=event_types,   # use [] if you want events off by default
        inline=True,
        style={"marginTop": "6px"}
    )
], className="col"),

            ], className="row")
        ], className="card"),

        # Charts card
        # Charts card
html.Div([
    html.Div("Trends and relationships", className="section-title"),
    
    dcc.Graph(
        id='time-series-plot',
        className="graph",
        style={"height": "520px"}, 
        config={"responsive": True, "displayModeBar": True, "scrollZoom": True},
        clear_on_unhover=True
    ),

    dcc.Graph(
        id='scatterplt',
        className="graph",
        style={"height": "520px"}, 
        config={"responsive": True, "displayModeBar": True, "scrollZoom": True},
        clear_on_unhover=True
    ),
    
], className="card"),


        # Radar card
        html.Div([
            html.Div("Radar comparison", className="section-title"),
            html.Div([
                html.Div([
                    html.Label("Select A:", className="label"),
                    dcc.Dropdown(
                        id='radar-a',
                        options=entity_options,
                        value=entity_options[0]['value'],
                        searchable=True,
                        clearable=False,
                        className="dropdown",
                    )
                ], className="col"),

                html.Div([
                    html.Label("Select B:", className="label"),
                    dcc.Dropdown(
                        id='radar-b',
                        options=entity_options,
                        value=entity_options[1]['value'] if len(entity_options) > 1 else entity_options[0]['value'],
                        searchable=True,
                        clearable=False,
                        className="dropdown",
                    )
                ], className="col"),
            ], className="row"),
        ], className="card"),

        html.Div(html.Div(id="radarplt"), className="card"),
        html.Div(id="radar-info", className="card"),

    ], className="page")
])


@app.callback(
    Output('scatterplt', 'figure'),
    Output('time-series-plot', 'figure'),
    Input('service-dropdown', 'value'),
    Input('metric-dropdown', 'value'),
    Input("event-checklist", "value")
)

def update_plot(service_selected, metrics_selected, selected_events):

  
    
        fig = go.Figure()
        fig_scatter = go.Figure() 
        if len(service_selected)==0 or len(metrics_selected)==0:
            fig.update_layout(
                title="Please select at least one service and one metric"
            )
            return fig_scatter, fig
        if len(service_selected) == 1:
            fig = make_subplots(rows=1, cols=1)
            positions = [[1,1]]
        elif len(service_selected)==2:
            fig = make_subplots(
            rows=1, cols=2,
            specs=[[{}, {}]])
            positions = [[1,1],[1,2]]
        elif len(service_selected)==3:
            fig = make_subplots(
            rows=2, cols=2,
            specs=[[{}, {}],
            [{}, {}]])
            positions = [[1,1],[1,2],[2,1]]
        elif len(service_selected)==4:
            fig = make_subplots(
            rows=2, cols=2,
            specs=[[{}, {}],
            [{}, {}]])
            positions = [[1,1],[1,2],[2,1],[2,2]]
        else:
            fig = make_subplots(
            rows=1, cols=1,
            specs=[[{}]])
            positions = [[1,1]]

        i=0
        show = False
        for s in service_selected:
            df_service = services[services['service'] == s]

            p = positions[i]
            i+=1
            

                
            # Add one line per selected metric
            for metric in metrics_selected:
                fig.add_trace(go.Scatter(
                    x=df_service['week'],
                    y=df_service[metric],
                    mode='lines+markers',
                    customdata=df_service['week'],
                    name=f"{s} — {metric}",
                    line=dict(color=SERVICE_COLORS[s],dash=metric_dash_map.get(metric, 'solid')),
                    marker=dict(color=SERVICE_COLORS[s]),
                    selected=dict(
                        marker=dict(opacity=1,color=SERVICE_COLORS_Selected[metric])
                        ),
                    unselected=dict(
                        marker=dict(opacity=0.15)
                        ),
                        
                    
                ),row=p[0],
                col=p[1])

            # Highlight events as shaded rectangles
            for event in selected_events:
                w = df_service.loc[df_service["event"] == event, "week"]
                w = pd.to_numeric(w, errors="coerce").dropna().unique()

                first = True   # only first rect shows legend entry

                for week in w:
                    fig.add_vrect(
                        x0=week - 0.5,
                        x1=week + 0.5,
                        fillcolor=event_color_map[event],
                        opacity=0.25,
                        layer="below",
                        line_width=0,
                        row=p[0],
                        col=p[1],

         # only once per event
                    )
                    first = False

        fig.update_layout(
                title=f"Metrics over time per service",
                xaxis_title="Week",
                yaxis_title="Value",
                legend_title="Metric"
            )

        # Scatter plot satisfaction vs patient-staff ratio
        fig_scatter = px.scatter(
            merged[merged['service'].isin(service_selected)],
            x='staff_to_patient_ratio',
            y='patient_satisfaction',
            custom_data=['week', 'service'],
            color='service',
            color_discrete_map=SERVICE_COLORS,
            size='staff_coverage',
            hover_data=['week', 'staff_coverage', 'patients_admitted', 'available_beds'],
            size_max=12,
            labels={
                'staff_to_patient_ratio': 'Staff / patient ratio',
                'patient_satisfaction': 'Patient satisfaction',
            },
            title=f'Staffing vs Patient Satisfaction'
        )
      


        fig.update_layout(dragmode='select', clickmode='event+select')
        fig_scatter.update_layout(dragmode='select', clickmode='event+select')
        
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
    app.run(debug=True, dev_tools_ui=True, dev_tools_props_check=True)



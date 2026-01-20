import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, State, Patch, ctx, no_update
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
services = pd.read_csv(r"Hospital Beds Management/services_weekly.csv")
df_HBM_patients        = pd.read_csv('Hospital Beds Management/patients.csv', delimiter=',', low_memory=False)
df_HBM_staff           = pd.read_csv('Hospital Beds Management/staff.csv', delimiter=',', low_memory=False)
df_HBM_staff_schedule  = pd.read_csv('Hospital Beds Management/staff_schedule.csv', delimiter=',', low_memory=False)
df_HBM_services_weekly = pd.read_csv('Hospital Beds Management/services_weekly.csv', delimiter=',', low_memory=False)


# Compute derived metrics
services['admits/requests'] = services['patients_admitted'] / services['patients_request']

# Categorize patient satisfaction and staff morale
def categorize_satisfaction(score):
    if score <= 20:
        return 'Very Low'
    elif score <= 40:
        return 'Low'
    elif score <= 60:
        return 'Medium'
    elif score <= 80:
        return 'High'
    else:
        return 'Very High'

services['patient_sat_cat'] = services['patient_satisfaction'].apply(categorize_satisfaction)
services['staff_morale_cat'] = services['staff_morale'].apply(categorize_satisfaction)

# Define categories
patient_sat_cats = ['Very Low', 'Low', 'Medium', 'High', 'Very High']
depts = services['service'].unique().tolist()
events = services['event'].unique().tolist()
staff_morale_cats = patient_sat_cats

# Node labels with explicit prefixes
patient_sat_labels = [f'Patient Satisfaction: {cat}' for cat in patient_sat_cats]
staff_morale_labels = [f'Staff Morale: {cat}' for cat in staff_morale_cats]
node_labels = patient_sat_labels + depts + events + staff_morale_labels

# Indices
num_sat = len(patient_sat_cats)
num_dept = len(depts)
num_event = len(events)

# Define color map for patient satisfaction categories
color_map = {
    'Very Low': 'red',
    'Low': 'yellow',
    'Medium': 'gray',
    'High': 'lightgreen',
    'Very High': 'darkgreen'
}

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

# Group by full path to create links per patient satisfaction category
grouped = services.groupby(['patient_sat_cat', 'service', 'event', 'staff_morale_cat']).size().reset_index(name='count')

# Links
links = []
for _, row in grouped.iterrows():
    sat = row['patient_sat_cat']
    dept = row['service']
    event = row['event']
    morale = row['staff_morale_cat']
    count = row['count']
    color = color_map[sat]
    
    sat_idx = patient_sat_cats.index(sat)
    dept_idx = num_sat + depts.index(dept)
    event_idx = num_sat + num_dept + events.index(event)
    morale_idx = num_sat + num_dept + num_event + staff_morale_cats.index(morale)
    
    links.append({'source': sat_idx, 'target': dept_idx, 'value': count, 'color': color})
    links.append({'source': dept_idx, 'target': event_idx, 'value': count, 'color': color})
    links.append({'source': event_idx, 'target': morale_idx, 'value': count, 'color': color})

# Node colors: patient satisfaction categories, departments, events with their respective colors, others neutral
node_colors = []
for label in node_labels:
    # Extract the category name without prefix
    if label.startswith('Patient Satisfaction: '):
        cat_name = label.replace('Patient Satisfaction: ', '')
        node_colors.append(color_map.get(cat_name, 'lightgray'))
    elif label.startswith('Staff Morale: '):
        cat_name = label.replace('Staff Morale: ', '')
        node_colors.append(color_map.get(cat_name, 'lightgray'))
    elif label in SERVICE_COLORS:
        node_colors.append(SERVICE_COLORS[label])
    elif label in event_color_map:
        node_colors.append(event_color_map[label])
    else:
        node_colors.append('lightgray')

# Link colors
link_colors = [l['color'] for l in links]

# Function to add opacity to colors
def add_opacity(color, opacity):
    color_map_rgb = {
        'red': '255,0,0',
        'yellow': '255,255,0',
        'gray': '128,128,128',
        'lightgray': '211,211,211',
        'lightgreen': '144,238,144',
        'darkgreen': '0,100,0',
        'lightblue': '173,216,230',
        'blue': '0,0,255',
        'purple': '128,0,128'
    }
    if color in color_map_rgb:
        return f'rgba({color_map_rgb[color]},{opacity})'
    elif color.startswith('rgba'):
        # If already rgba, update alpha
        parts = color.strip('rgba()').split(',')
        parts[-1] = str(opacity)
        return f'rgba({",".join(parts)})'
    elif color.startswith('rgb'):
        # Convert rgb to rgba
        rgb_part = color.strip('rgb()')
        return f'rgba({rgb_part},{opacity})'
    else:
        return f'rgba(128,128,128,{opacity})'  # default gray

# Initial Sankey figure with default opacity
initial_opacity = 0.5
link_colors_opacity = [add_opacity(c, initial_opacity) for c in link_colors]
fig_sankey = go.Figure(go.Sankey(
    node=dict(
        pad=15,
        thickness=20,
        line=dict(color="black", width=0.5),
        label=node_labels,
        color=node_colors
    ),
    link=dict(
        source=[l['source'] for l in links],
        target=[l['target'] for l in links],
        value=[l['value'] for l in links],
        color=link_colors_opacity
    )
))
fig_sankey.update_layout(title_text="Patient Satisfaction Flow", font_size=10)

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

# Combine them (averages first so they’re easy to find)
entity_options = avg_options + staff_options

radar_norm_cols = [c + "_norm" for c in radar_cols]

# Calculate patient metrics for patient radar chart
df_HBM_patients['arrival_date'] = pd.to_datetime(df_HBM_patients['arrival_date'])
df_HBM_patients['departure_date'] = pd.to_datetime(df_HBM_patients['departure_date'])
df_HBM_patients['days_admitted'] = (df_HBM_patients['departure_date'] - df_HBM_patients['arrival_date']).dt.days + 1

# Estimate which week the patient was admitted (assuming year starts Jan 1, week 1)
# Simple assumption: each week is 7 days, year starts from week 1 on Jan 1
df_HBM_patients['admission_day_of_year'] = df_HBM_patients['arrival_date'].dt.dayofyear
df_HBM_patients['departure_day_of_year'] = df_HBM_patients['departure_date'].dt.dayofyear
df_HBM_patients['admission_week'] = ((df_HBM_patients['admission_day_of_year'] - 1) // 7) + 1
df_HBM_patients['departure_week'] = ((df_HBM_patients['departure_day_of_year'] - 1) // 7) + 1

patient_metrics = []
for _, pat in df_HBM_patients.iterrows():
    pat_id = pat['patient_id']
    pat_name = pat['name']
    pat_satisfaction = pat['satisfaction']
    service = pat['service']
    admission_week = pat['admission_week']
    departure_week = pat['departure_week']
    days_admitted = pat['days_admitted']
    
    # Get weeks during patient stay
    weeks_during_stay = df_HBM_services_weekly[
        (df_HBM_services_weekly['week'] >= admission_week) & 
        (df_HBM_services_weekly['week'] <= departure_week) &
        (df_HBM_services_weekly['service'] == service)
    ]
    
    if len(weeks_during_stay) == 0:
        continue
    
    # Count events during stay (events that are not 'none')
    num_events = len(weeks_during_stay[weeks_during_stay['event'] != 'none'])
    
    # Average staff morale during stay
    avg_staff_morale = weeks_during_stay['staff_morale'].mean()
    
    # Average available beds during stay
    avg_available_beds = weeks_during_stay['available_beds'].mean()
    
    # Patients per staff: patients_admitted / staff_coverage
    # Calculate from the services data - assume staff coverage relates to workload
    avg_patients_admitted = weeks_during_stay['patients_admitted'].mean()
    patients_per_staff = avg_patients_admitted / len(weeks_during_stay) if len(weeks_during_stay) > 0 else 0
    
    patient_metrics.append({
        'patient_id': pat_id,
        'patient_name': pat_name,
        'satisfaction': pat_satisfaction,
        'service': service,
        'days_admitted': days_admitted,
        'num_events': num_events,
        'avg_staff_morale': avg_staff_morale,
        'avg_available_beds': avg_available_beds,
        'patients_per_staff': patients_per_staff
    })

df_patient_metrics = pd.DataFrame(patient_metrics)

# Categorize patients by satisfaction
# Use percentiles instead of fixed thresholds since satisfaction ranges 60-99
lowest_threshold = df_patient_metrics['satisfaction'].quantile(0.25)  # Bottom 25%
highest_threshold = df_patient_metrics['satisfaction'].quantile(0.75)  # Top 25%

highest_sat_patients = df_patient_metrics[df_patient_metrics['satisfaction'] >= highest_threshold]
lowest_sat_patients = df_patient_metrics[df_patient_metrics['satisfaction'] <= lowest_threshold]

# Create options for dropdowns
highest_options = [
    {'label': f"{row['patient_name']} (Satisfaction: {row['satisfaction']})", 
     'value': row['patient_id']}
    for _, row in highest_sat_patients.iterrows()
]
highest_options = sorted(highest_options, key=lambda x: x['label'])

lowest_options = [
    {'label': f"{row['patient_name']} (Satisfaction: {row['satisfaction']})", 
     'value': row['patient_id']}
    for _, row in lowest_sat_patients.iterrows()
]
lowest_options = sorted(lowest_options, key=lambda x: x['label'])

# Patient radar columns
patient_radar_cols = ['days_admitted', 'num_events', 'avg_staff_morale', 'avg_available_beds', 'patients_per_staff']
patient_radar_labels = ['Days Admitted', '# Events', 'Staff Morale', 'Available Beds', 'Patients per Staff']

# Normalize patient metrics
df_patient_norm = df_patient_metrics.copy()
for col in patient_radar_cols:
    col_data = df_patient_norm[col]
    m_min, m_max = col_data.min(), col_data.max()
    if m_max == m_min:
        df_patient_norm[col + '_norm'] = 0.5
    else:
        df_patient_norm[col + '_norm'] = (col_data - m_min) / (m_max - m_min)
app = Dash(__name__)

app.layout = html.Div([
    html.Div([  # page

    html.Div([
        html.H1("Hospital Metrics Over Time", className="h1"),
        html.Div("Hover for details • Select to compare • Scroll to zoom", className="sub"),
    ], className="header"),

    dcc.Tabs(
        id="main-tabs",
        value="tab-trends",
        children=[
                        dcc.Tab(
                label="Staff analysis",
                value="tab-staff",
                children=[
                    html.Div([
                        html.Div("Patient satifaction overview", className="section-title"),
                        html.Div("Coming soon…", className="sub"),
                    ], className="card"),
                ],
            ),
            # ---------------- TAB 1 ----------------
            dcc.Tab(
                label="Trends & relationships",
                value="tab-trends",
                children=[

                    # Controls card (SERVICE / METRIC / EVENTS) - ONLY IN TAB 1
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
                                    value=event_types,  # [] if you want off by default
                                    inline=True,
                                    style={"marginTop": "6px"}
                                )
                            ], className="col"),

                        ], className="row")
                    ], className="card"),

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

                    # Spider chart for clicked scatter plot point
                    html.Div(id='spider-chart-container', style={'display': 'none'}, children=[
                        html.Div([
                            html.Div("Service Profile Comparison", className="section-title"),
                            html.Div(html.Div(id="spider-chart-plot"), className="card"),
                            html.Div(id="spider-chart-info", className="card"),
                        ], className="card"),
                    ]),

                    # Pie chart for staff assignment for clicked week
                    html.Div(id='pie-chart-container', style={'display': 'none'}, children=[
                        html.Div([
                            html.Div("Staff Assignment Analysis", className="section-title"),
                            html.Div(dcc.Graph(id="staff-assignment-pie", className="graph", style={"height": "500px"}, config={"responsive": True, "displayModeBar": True}), className="card"),
                        ], className="card"),
                    ]),

                        dcc.Store(id="selected-weeks")
                ],
            ),

            # ---------------- TAB 2 ----------------
            dcc.Tab(
                label="Radar comparison",
                value="tab-radar",
                children=[

                    # Radar controls - ONLY IN TAB 2
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
                ],
            ),

            


            # ---------------- TAB 4 ----------------
            dcc.Tab(
                label="Patient satisfaction flow",
                value="tab-notes",
                children=[
                    html.Div([
                        html.Div("Patient Satisfaction Flow", className="section-title"),
                        
                        html.Div([
                            html.Div([
                                html.Label("Select Category:", className="label"),
                                dcc.Dropdown(
                                    id='sankey-category-dropdown',
                                    options=[{'label': 'All', 'value': 'All'}] + [{'label': cat, 'value': cat} for cat in patient_sat_cats],
                                    value='All',
                                    clearable=False,
                                    className="dropdown",
                                )
                            ], className="col"),
                            
                            html.Div([
                                html.Label("Filter Mode:", className="label"),
                                dcc.Checklist(
                                    id='sankey-filter-toggle',
                                    options=[{'label': ' Show only this category', 'value': 'filter'}],
                                    value=[],
                                    inline=True,
                                    style={"marginTop": "6px"}
                                )
                            ], className="col"),
                        ], className="row"),
                        
                        html.P("Link Opacity", className="label"),
                        dcc.Slider(id='sankey-opacity', min=0, max=1, value=0.5, step=0.1),
                        
                        dcc.Graph(id='sankey', className="graph", style={"height": "600px"}),
                    ], className="card"),
                ],
            ),
        ],
    ),

], className="page")])

@app.callback(
    Output("selected-weeks", "data"),
    Input("time-series-plot", "selectedData"),
    Input("scatterplt", "selectedData"),
    prevent_initial_call=True,
)

def update_selected_weeks(selectedData1,selectedData2):

    # If nothing is selected there is nothing to update
    if not selectedData1 and not selectedData2:
        return no_update
    
    # Get and store selected weeks
    selected = []
    if selectedData1 is not None:
        selected = [p["x"] for p in selectedData1["points"] if p.get("x") is not None]
    if selectedData2 is not None:
        selected = selected+ [p.get("customdata")[0] for p in selectedData2["points"] if p.get("customdata") is not None]
    
    return selected

@app.callback(
    Output('scatterplt', 'figure'),
    Output('time-series-plot', 'figure'),
    Input('service-dropdown', 'value'),
    Input('metric-dropdown', 'value'),
    Input("event-checklist", "value"),
    Input("selected-weeks", "data"),
    State('time-series-plot', 'figure'),  
    State('scatterplt', 'figure')
)

def update_plot(service_selected, metrics_selected, selected_events,selected_weeks,c_fig,c_scat):
        
        # If callback happend due to selection do not update whole figure.
        triggered_id = ctx.triggered_id
        if triggered_id == "selected-weeks":
            if not selected_weeks:
                 return no_update, no_update
        
        fig = go.Figure()
        fig_scatter = go.Figure() 

        # If no services or metric selected ask for atleast one
        if len(service_selected)==0 or len(metrics_selected)==0:
            fig.update_layout(
                title="Please select at least one service and one metric"
            )
            return fig_scatter, fig
        
        # Construct the correct amount of subplots per selected service
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

        # Fill the subplot for each service
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
                    selectedpoints=[i for i, w in enumerate(df_service['week']) if selected_weeks and w in selected_weeks],
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

                    )
                    

        fig.update_layout(
                title=f"Metrics over time per service",
                xaxis_title="Week",
                yaxis_title="Value",
                legend_title="Metric",
            )
        
        scatter_data = merged[merged['service'].isin(service_selected)]
       
        # Scatter plot satisfaction vs patient-staff ratio
        fig_scatter = px.scatter(
            scatter_data,
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

        # Sync and highlight the selected data
        selectedpointsRatio = [i for i, w in enumerate(scatter_data['week']) if selected_weeks and w in selected_weeks]
        if selectedpointsRatio is not None:
         for trace in fig_scatter.data:
            trace.selectedpoints = selectedpointsRatio
            trace.selected = dict(marker=dict(opacity=1, size=14))
            trace.unselected = dict(marker=dict(opacity=0.3))

        fig.update_layout( dragmode='select', clickmode='event+select')
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

@app.callback(
    Output("sankey", "figure"),
    Input("sankey-opacity", "value"),
    Input("sankey-category-dropdown", "value"),
    Input("sankey-filter-toggle", "value")
)
def update_sankey(opacity, selected_cat, filter_enabled):
    is_filter_mode = len(filter_enabled) > 0
    
    if is_filter_mode and selected_cat != 'All':
        # FILTER MODE: Show only selected category
        filtered_grouped = grouped[grouped['patient_sat_cat'] == selected_cat]
        
        # Build filtered node labels and indices
        filtered_sat_cats = [selected_cat]
        filtered_depts = filtered_grouped['service'].unique().tolist()
        filtered_events = filtered_grouped['event'].unique().tolist()
        filtered_morale_cats = filtered_grouped['staff_morale_cat'].unique().tolist()
        
        filtered_patient_sat_labels = [f'Patient Satisfaction: {cat}' for cat in filtered_sat_cats]
        filtered_staff_morale_labels = [f'Staff Morale: {cat}' for cat in filtered_morale_cats]
        filtered_node_labels = filtered_patient_sat_labels + filtered_depts + filtered_events + filtered_staff_morale_labels
        
        num_sat_f = len(filtered_sat_cats)
        num_dept_f = len(filtered_depts)
        num_event_f = len(filtered_events)
        
        # Build filtered node colors
        filtered_node_colors = []
        for label in filtered_node_labels:
            # Extract the category name without prefix
            if label.startswith('Patient Satisfaction: '):
                cat_name = label.replace('Patient Satisfaction: ', '')
                filtered_node_colors.append(color_map.get(cat_name, 'lightgray'))
            elif label.startswith('Staff Morale: '):
                cat_name = label.replace('Staff Morale: ', '')
                filtered_node_colors.append(color_map.get(cat_name, 'lightgray'))
            elif label in SERVICE_COLORS:
                filtered_node_colors.append(SERVICE_COLORS[label])
            elif label in event_color_map:
                filtered_node_colors.append(event_color_map[label])
            else:
                filtered_node_colors.append('lightgray')
        
        links = []
        for _, row in filtered_grouped.iterrows():
            sat = row['patient_sat_cat']
            dept = row['service']
            event = row['event']
            morale = row['staff_morale_cat']
            count = row['count']
            
            color_sat_to_dept = color_map[sat]
            color_dept_to_event = SERVICE_COLORS.get(dept, 'blue')
            color_event_to_morale = event_color_map.get(event, 'gray')
            
            sat_idx = filtered_sat_cats.index(sat)
            dept_idx = num_sat_f + filtered_depts.index(dept)
            event_idx = num_sat_f + num_dept_f + filtered_events.index(event)
            morale_idx = num_sat_f + num_dept_f + num_event_f + filtered_morale_cats.index(morale)
            
            links.append({'source': sat_idx, 'target': dept_idx, 'value': count, 'color': color_sat_to_dept, 'sat': sat})
            links.append({'source': dept_idx, 'target': event_idx, 'value': count, 'color': color_dept_to_event, 'sat': sat})
            links.append({'source': event_idx, 'target': morale_idx, 'value': count, 'color': color_event_to_morale, 'sat': sat})
        
        node_labels_to_use = filtered_node_labels
        node_colors_to_use = filtered_node_colors
        title_text = f"Patient Satisfaction Flow - {selected_cat}"
        
    else:
        # HIGHLIGHT MODE: Show all categories, highlight selected one
        filtered_grouped = grouped
        
        links = []
        for _, row in filtered_grouped.iterrows():
            sat = row['patient_sat_cat']
            dept = row['service']
            event = row['event']
            morale = row['staff_morale_cat']
            count = row['count']
            
            color_sat_to_dept = color_map[sat]
            color_dept_to_event = SERVICE_COLORS.get(dept, 'blue')
            color_event_to_morale = event_color_map.get(event, 'gray')
            
            # Gray out other categories if one is selected
            if selected_cat != 'All' and sat != selected_cat:
                color_sat_to_dept = 'lightgray'
                color_dept_to_event = 'lightgray'
                color_event_to_morale = 'lightgray'
            
            sat_idx = patient_sat_cats.index(sat)
            dept_idx = num_sat + depts.index(dept)
            event_idx = num_sat + num_dept + events.index(event)
            morale_idx = num_sat + num_dept + num_event + staff_morale_cats.index(morale)
            
            links.append({'source': sat_idx, 'target': dept_idx, 'value': count, 'color': color_sat_to_dept, 'sat': sat})
            links.append({'source': dept_idx, 'target': event_idx, 'value': count, 'color': color_dept_to_event, 'sat': sat})
            links.append({'source': event_idx, 'target': morale_idx, 'value': count, 'color': color_event_to_morale, 'sat': sat})
        
        node_labels_to_use = node_labels
        node_colors_to_use = node_colors
        title_text = "Patient Satisfaction Flow"
        if selected_cat != 'All':
            title_text += f" - Highlighting: {selected_cat}"
    
    link_colors = [l['color'] for l in links]
    link_customdata = [l['sat'] for l in links]
    link_colors_opacity = [add_opacity(c, opacity) for c in link_colors]
    
    fig = go.Figure(go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=node_labels_to_use,
            color=node_colors_to_use
        ),
        link=dict(
            source=[l['source'] for l in links],
            target=[l['target'] for l in links],
            value=[l['value'] for l in links],
            color=link_colors_opacity,
            customdata=link_customdata,
            hovertemplate='Source: %{source.label}<br>Target: %{target.label}<br>Value: %{value}<br>Patient Satisfaction: %{customdata}<extra></extra>'
        )
    ))
    fig.update_layout(title_text=title_text, font_size=10)
    return fig

@app.callback(
    Output('spider-chart-container', 'style'),
    Output('spider-chart-plot', 'children'),
    Output('spider-chart-info', 'children'),
    Input('scatterplt', 'clickData'),
)
def update_spider_chart(clickData):
    if clickData is None or len(clickData.get('points', [])) == 0:
        return {'display': 'none'}, '', ''
    
    # Extract data from clicked point
    point = clickData['points'][0]
    week = point.get('customdata', [None, None])[0]
    service = point.get('customdata', [None, None])[1] if len(point.get('customdata', [])) > 1 else None
    
    if week is None or service is None:
        return {'display': 'none'}, '', ''
    
    # Get the data for this specific week/service
    week_service_data = services[(services['week'] == week) & (services['service'] == service)]
    
    if week_service_data.empty:
        return {'display': 'none'}, '', ''
    
    week_service_data = week_service_data.iloc[0]
    
    # Calculate average values across all weeks/services
    avg_satisfaction = services['patient_satisfaction'].mean()
    avg_morale = services['staff_morale'].mean()
    avg_beds = services['available_beds'].mean()
    avg_admits_req = (services['patients_admitted'] / services['patients_request']).mean()
    avg_patients = services['patients_admitted'].mean()
    
    # Normalize values to 0-1 scale
    def normalize(value, col_name):
        col_data = services[col_name]
        min_val, max_val = col_data.min(), col_data.max()
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)
    
    # Current week/service profile
    current_vals = [
        normalize(week_service_data['patient_satisfaction'], 'patient_satisfaction'),
        normalize(week_service_data['staff_morale'], 'staff_morale'),
        normalize(week_service_data['available_beds'], 'available_beds'),
        normalize(week_service_data['admits/requests'], 'admits/requests'),
        normalize(week_service_data['patients_admitted'], 'patients_admitted'),
    ]
    
    # Average profile
    avg_vals = [
        normalize(avg_satisfaction, 'patient_satisfaction'),
        normalize(avg_morale, 'staff_morale'),
        normalize(avg_beds, 'available_beds'),
        normalize(avg_admits_req, 'admits/requests'),
        normalize(avg_patients, 'patients_admitted'),
    ]
    
    labels = ['Patient Satisfaction', 'Staff Morale', 'Available Beds', 'Admits/Requests', 'Patients Admitted']
    n = len(labels)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    angles = np.r_[angles, angles[0]]
    
    current_vals_plot = np.r_[current_vals, current_vals[0]]
    avg_vals_plot = np.r_[avg_vals, avg_vals[0]]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.set_ylim(0, 1)
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    
    ax.plot(angles, current_vals_plot, linewidth=2, marker="o")
    ax.fill(angles, current_vals_plot, alpha=0.25, label=f"{service} - Week {week}")
    
    ax.plot(angles, avg_vals_plot, linewidth=2, marker="^", linestyle='--')
    ax.fill(angles, avg_vals_plot, alpha=0.1, label="Average")
    
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), frameon=False)
    ax.set_title("Service profile comparison", pad=18)
    
    def fig_to_data_uri(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        data = base64.b64encode(buf.getvalue()).decode("utf-8")
        return "data:image/png;base64," + data
    
    img = html.Img(src=fig_to_data_uri(fig), style={"width": "100%", "maxWidth": "650px"})
    
    info_box = html.Div([
        html.Div([
            html.B("Selected: "), html.Span(f"{service} - Week {week}"), html.Br(),
            html.Span(f"Satisfaction: {week_service_data['patient_satisfaction']:.1f}"), html.Br(),
            html.Span(f"Staff Morale: {week_service_data['staff_morale']:.1f}"), html.Br(),
            html.Span(f"Available Beds: {week_service_data['available_beds']:.0f}"),
        ], style={'width': '48%', 'display': 'inline-block'}),
        
        html.Div([
            html.B("Average: "), html.Span("All Services"), html.Br(),
            html.Span(f"Satisfaction: {avg_satisfaction:.1f}"), html.Br(),
            html.Span(f"Staff Morale: {avg_morale:.1f}"), html.Br(),
            html.Span(f"Available Beds: {avg_beds:.0f}"),
        ], style={'width': '48%', 'display': 'inline-block', 'marginLeft': '4%'}),
    ])
    
    return {'display': 'block'}, img, info_box



if __name__ == '__main__':
    webbrowser.open("http://127.0.0.1:8050/")
    app.run(debug=True, dev_tools_ui=True, dev_tools_props_check=True)



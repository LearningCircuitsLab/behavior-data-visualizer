# create a dash app to visualize the behavior data using plotly
import dash
import plotly.express as px
import pandas as pd
import numpy as np
from pathlib import Path
from lecilab_behavior_analysis import df_transforms as dft

# Load the data
outpath = "/mnt/c/Users/HMARTINEZ/LeCiLab/data"
# go through the tree and get the data
data_dict = {}
for path in Path(outpath).rglob('*.csv'):
    data = pd.read_csv(path, sep=';')
    mouse_name = path.parts[-2]
    data_dict[mouse_name] = data

# Create the app
app = dash.Dash(__name__)

# Create the layout
app.layout = dash.html.Div([
    dash.html.H1("Behavior Data Visualization"),
    dash.dcc.Checklist(
        id='dropdown',
        options=[{'label': key, 'value': key} for key in data_dict.keys()],
        value=[list(data_dict.keys())[0]],
        labelStyle={'display': 'block'}
    ),
    dash.dcc.Graph(id='graph')
])

# Create the callback
@app.callback(
    dash.dependencies.Output('graph', 'figure'),
    [dash.dependencies.Input('dropdown', 'value')]
)

def update_figure(selected_value):
    # merge the datasets of the selected mice
    tdfs = []
    for key in selected_value:
        df = data_dict[key]
        df["mouse_name"] = key
        tdfs.append(dft.get_performance_through_trials(df, window=50))
    tdf = pd.concat(tdfs)
    fig = px.line(tdf, x='total_trial', y='performance_w', color='mouse_name')
    return fig

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)


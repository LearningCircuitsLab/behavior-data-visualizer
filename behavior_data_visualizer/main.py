# create a dash app to visualize the behavior data using plotly
import dash
import plotly.express as px
from plotly_calplot import calplot
import pandas as pd
from pathlib import Path
from lecilab_behavior_analysis import df_transforms as dft
from lecilab_behavior_analysis import figure_maker as fm
from lecilab_behavior_analysis import utils as lbaut
from behavior_data_visualizer import utils
import fire


# Create the app
def app_builder(mouse_data_dict):
    # create an empty dictionary for the session data
    session_data_dict = {}

    app = dash.Dash(__name__)

    # Create the layout
    app.layout = dash.html.Div([
        dash.dcc.Tabs([
            dash.dcc.Tab(label='Compare mice', children=[
                dash.dcc.Checklist(
                    id='mice-checklist',
                    options=[{'label': key, 'value': key} for key in mouse_data_dict.keys()],
                    value=[],
                    labelStyle={'display': 'block'}
                ),
                dash.dcc.Graph(id='graph')
            ]),

            dash.dcc.Tab(label='Single mouse reactive', children=[
                dash.dcc.Dropdown(
                    id='single-mouse-dropdown',
                    options=[{'label': key, 'value': key} for key in mouse_data_dict.keys()],
                    value=None,
                    multi=False,
                    style={'width': '30%'}
                ),
                dash.dcc.Graph(id='reactive-calendar', style={'width': '100%'}),
                dash.html.Div([
                    dash.html.Pre(id='single-mouse-text', style={'flex': '1'}),
                    dash.dcc.Graph(id='single-mouse-performance', style={'flex': '1', 'height': '15%'}),
                    dash.dcc.Graph(id="single-mouse-psychometric", style={'flex': '1', 'height': '15%'}),
                ], style={'display': 'flex', 'flex-direction': 'row'}),
            ]),

            dash.dcc.Tab(label='Reports', children=[
                dash.html.H3('Subject progress'),
                dash.dcc.Dropdown(
                    id='reports-mice-dropdown',
                    options=[{'label': key, 'value': key} for key in mouse_data_dict.keys()],
                    value=None,
                    multi=False,
                    style={'width': '30%'}
                ),
                dash.html.Img(id='subject-progress', src=''),
                dash.html.H3('Session summary'),
                dash.dcc.Dropdown(
                    id='reports-session-dropdown',
                    options=[{'label': key, 'value': session_data_dict[key]} for key in session_data_dict.keys()],
                    value=None,
                    multi=False,
                    style={'width': '30%'}
                ),
                dash.html.Img(id='session-summary', src=''),
            ]),
        ])
    ])

    # Callback for the mouse comparison
    @app.callback(
        dash.dependencies.Output('graph', 'figure'),
        [dash.dependencies.Input('mice-checklist', 'value')],
    )
    def update_figure(selected_items):
        if len(selected_items) == 0:
            return {}
        # merge the datasets of the selected mice
        tdfs = []
        for key in selected_items:
            df = mouse_data_dict[key]
            df["mouse_name"] = key
            tdfs.append(dft.get_performance_through_trials(df, window=50))
        tdf = pd.concat(tdfs)
        fig = px.line(tdf, x='total_trial', y='performance_w', color='mouse_name')
        return fig

    # Callbacks for the single mouse reactive
    @app.callback(
        dash.dependencies.Output('reactive-calendar', 'figure'),
        [dash.dependencies.Input('single-mouse-dropdown', 'value')],
    )
    def update_calendar(mouse_name):
        if mouse_name is None:
            return {}
        df = mouse_data_dict[mouse_name]

        dates_df = df.groupby(["year_month_day"]).count().reset_index()

        fig = calplot(
            dates_df,
            x='year_month_day',
            y='trial',
            # text="year_month_day",
        )
        return fig

    # Update the figures with the click data
    @app.callback(
        dash.dependencies.Output('single-mouse-text', 'children'),
        dash.dependencies.Output('single-mouse-performance', 'figure'),
        dash.dependencies.Output('single-mouse-psychometric', 'figure'),
        [dash.dependencies.Input('reactive-calendar', 'clickData'),
        dash.dependencies.Input('single-mouse-dropdown', 'value')],
    )
    def update_single_mouse_reactive(clickData, mouse_name):
        text = utils.display_click_data(clickData, mouse_name)
        perf_fig = utils.update_performance_figure(clickData, mouse_name)
        psych_fig = utils.update_psychometric_figure(clickData, mouse_name)
        return text, perf_fig, psych_fig


    # Callback for the reports
    # Figure for the subject progress
    @app.callback(
        dash.dependencies.Output('subject-progress', component_property='src'),
        [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    )
    def update_subject_progress(selected_value):
        if selected_value is None:
            return ''
        df = mouse_data_dict[selected_value]
        fig = fm.subject_progress_figure(df, selected_value)
        return utils.fig_to_uri(fig)

    # Dropdown for the sessions
    @app.callback(
        dash.dependencies.Output('reports-session-dropdown', 'options'),
        [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    )
    def update_session_dropdown(selected_value):
        if selected_value is None:
            return []
        df = mouse_data_dict[selected_value]
        session_data_dict = utils.get_dicctionary_of_sessions(df)
        return [{'label': key, 'value': session_data_dict[key]} for key in session_data_dict.keys()]

    # Figure for the session summary
    @app.callback(
        dash.dependencies.Output('session-summary', component_property='src'),
        [dash.dependencies.Input('reports-mice-dropdown', 'value')],
        [dash.dependencies.Input('reports-session-dropdown', 'value')],
    )
    def update_session_summary(mouse, session):
        if mouse is None or session is None:
            return ''
        df = mouse_data_dict[mouse]
        sdf = df[df["session"] == session]
        fig = fm.session_summary_figure(sdf, mouse, perf_window=100)
        return utils.fig_to_uri(fig)

    return app

def get_mouse_data_dict(project_name):
    # Load the data
    outpath = utils.get_data_path() + project_name + "/sessions/"
    # go through the tree and get the data
    mouse_data_dict = {}
    
    # get the animals from the path
    for path in Path(outpath).iterdir():
        # check if the path is a directory
        if path.is_dir():
            # check if the path has a csv file
            if any(path.glob(f'{path.name}.csv')):
                # read that csv file
                data = pd.read_csv(path / f'{path.name}.csv', sep=';')
                # add columns
                data = dft.add_day_column_to_df(data)
                # add it to the dictionary
                mouse_data_dict[path.name] = data
    # pass it to utils to make it global
    utils.set_mouse_data_dict(mouse_data_dict)
    # return the data
    return mouse_data_dict

# Run the app
if __name__ == '__main__':
    # Get the data
    # Fire(get_mouse_data_dict)
    mouse_data_dict = get_mouse_data_dict("visual_and_COT_data")
    # Build the app
    app = app_builder(mouse_data_dict)
    # Run the app
    app.run_server(debug=True)


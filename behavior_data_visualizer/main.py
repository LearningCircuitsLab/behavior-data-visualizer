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
import os
from flask import send_from_directory
from dash.exceptions import PreventUpdate

# Serve static files (e.g., videos)
STATIC_PATH = os.path.join(os.getcwd(), 'static')
if not os.path.exists(STATIC_PATH):
    os.makedirs(STATIC_PATH)

def app_builder(project_name):
    mouse_data_dict = utils.get_mouse_data_dict(project_name)
    session_data_dict = {}

    app = dash.Dash(__name__)

    # Serve static files route
    @app.server.route('/videos/<path:filename>')
    def serve_video(filename):
        return send_from_directory(STATIC_PATH, filename)

    # Clientside callback to set video start time
    app.clientside_callback(
        """
        function(startData) {
            const video = document.getElementById("video-player");
            if (video && startData && startData.time !== undefined) {
                const setTime = () => {
                    if (video.readyState >= 1) {
                        video.currentTime = startData.time;
                        video.play();
                    } else {
                        video.addEventListener('loadedmetadata', () => {
                            video.currentTime = startData.time;
                            video.play();
                        });
                    }
                };
                setTimeout(setTime, 500);
            }
            return window.dash_clientside.no_update;
        }
        """,
        dash.Output("video-start-time", "data"),
        dash.Input("video-start-time", "data")
    )

    # Layout
    app.layout = dash.html.Div([
        dash.dcc.Store(id="video-start-time"),  # Declare globally in layout

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
                dash.html.Div([
                    dash.dcc.Dropdown(
                        id='single-mouse-dropdown',
                        options=[{'label': key, 'value': key} for key in mouse_data_dict.keys()],
                        value=None,
                        multi=False,
                        style={'width': '10%'}
                    ),
                    dash.dcc.Graph(id='reactive-calendar', style={'width': '55%'}),
                    dash.html.Pre(id='single-mouse-text', style={'flex': '1', 'width': '35%'}),
                ], style={'display': 'flex', 'flex-direction': 'row'}),
                dash.html.Div([
                    dash.dcc.Graph(id='single-mouse-performance', style={'flex': '1', 'height': '15%', 'width': '35%'}),
                    dash.dcc.Graph(id="single-mouse-psychometric", style={'flex': '1', 'height': '15%', 'width': '20%'}),
                    dash.html.Pre(id='single-mouse-video', style={'display': 'flex', 'flex-direction': 'row', 'flex': '1', 'width': '45%'}),
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

    @app.callback(
        dash.dependencies.Output('graph', 'figure'),
        [dash.dependencies.Input('mice-checklist', 'value')],
    )
    def update_figure(selected_items):
        if len(selected_items) == 0:
            return {}
        tdfs = []
        for key in selected_items:
            df = mouse_data_dict[key]
            df["mouse_name"] = key
            tdfs.append(dft.get_performance_through_trials(df, window=50))
        tdf = pd.concat(tdfs)
        fig = px.line(tdf, x='total_trial', y='performance_w', color='mouse_name')
        return fig

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
        )
        return fig

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

    @app.callback(
        dash.dependencies.Output('single-mouse-video', 'children'),
        dash.dependencies.Output('video-start-time', 'data', allow_duplicate=True),
        [dash.dependencies.Input('single-mouse-performance', 'clickData')],
        prevent_initial_call=True
    )
    def update_single_mouse_video(clickData):
        if clickData is None:
            raise PreventUpdate

        try:
            subject, task, date, trial = clickData['points'][0]['customdata']
            video_path = utils.get_video_path(project_name, subject, task, date, trial)
        except (KeyError, TypeError):
            return dash.html.Div("Invalid click data"), dash.no_update

        if not os.path.exists(video_path):
            return dash.html.Div(f"Video file not found: {video_path}"), dash.no_update

        video_filename = os.path.basename(video_path)
        static_video_path = os.path.join(STATIC_PATH, video_filename)
        if not os.path.exists(static_video_path):
            try:
                os.symlink(video_path, static_video_path)
            except OSError as e:
                return dash.html.Div(f"Error linking video: {e}"), dash.no_update

        # convert trial to seconds
        start_time = utils.get_seconds_of_trial(subject, date, trial)
        video_component = dash.html.Video(
            id="video-player",
            src=f"/videos/{video_filename}",
            controls=True,
            autoPlay=True,
            muted=True,
            style={"width": "100%"},
        )

        return video_component, {"time": start_time}

    @app.callback(
        dash.dependencies.Output('subject-progress', component_property='src'),
        [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    )
    def update_subject_progress(selected_value):
        if selected_value is None:
            return ''
        df = mouse_data_dict[selected_value]
        fig = fm.subject_progress_figure(df)
        return utils.fig_to_uri(fig)

    @app.callback(
        dash.dependencies.Output('reports-session-dropdown', 'options'),
        [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    )
    def update_session_dropdown(selected_value):
        if selected_value is None:
            return []
        df = mouse_data_dict[selected_value]
        session_data_dict = utils.get_diccionary_of_dates(df)
        return [{'label': key, 'value': session_data_dict[key]} for key in session_data_dict.keys()]

    @app.callback(
        dash.dependencies.Output('session-summary', component_property='src'),
        [dash.dependencies.Input('reports-mice-dropdown', 'value')],
        [dash.dependencies.Input('reports-session-dropdown', 'value')],
    )
    def update_session_summary(mouse, session):
        if mouse is None or session is None:
            return ''
        df = mouse_data_dict[mouse]
        sdf = df[df["year_month_day"] == session]
        fig = fm.session_summary_figure(sdf, mouse, perf_window=25)
        return utils.fig_to_uri(fig)

    return app

if __name__ == '__main__':
    app = app_builder('visual_and_COT_data')
    app.run(debug=True, port=8050)

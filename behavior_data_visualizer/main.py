"""
Training Village Behavior Explorer: a dash app to look at the behavior of
the mice of a project, day by day.

Choose a project and a mouse; the calendar shows its days with trials.
Click a day to see its summary, its performance, its psychometric curves
(one per stimulus modality) and what happened on each trial (stimulus,
outcome, early pokeouts). Click a trial in the performance or in the
trial-by-trial figure to watch the video from that trial. Zoom on some
trials in either figure to see the same trials in the other one, and the
psychometric curves of those trials only. The buttons draw the figures of the daily
report: the session summary of the day and the training history up to it.

Run it with: python behavior_data_visualizer/main.py (http://127.0.0.1:8050).
The data is read from the folder of lecilab_behavior_analysis (the
LECILAB_DATA_PATH environment variable, or the folder of this computer).
"""

import os
import threading
from pathlib import Path

import dash
from dash import dcc, html
from dash.exceptions import PreventUpdate
from flask import send_from_directory

from behavior_data_visualizer import data, figures

# videos are linked here to be served by the app (/videos/<file>)
STATIC_PATH = Path(__file__).resolve().parents[1] / "static"

# matplotlib is not thread safe: one report figure at a time
REPORT_LOCK = threading.Lock()

ROW = {"display": "flex", "flex-direction": "row", "gap": "8px", "align-items": "flex-start"}
SMALL_TEXT = {"margin-top": "8px", "font-size": "11px", "color": "grey", "word-break": "break-all"}
BUTTON = {"margin-right": "8px", "padding": "6px 12px", "cursor": "pointer"}


def app_builder():
    STATIC_PATH.mkdir(exist_ok=True)

    # get the list of the projects
    projects_list = data.get_list_of_projects()
    data_path = data.get_data_path()

    app = dash.Dash(__name__, title="Behavior Explorer")

    # Serve static files route
    @app.server.route("/videos/<path:filename>")
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
        dash.Input("video-start-time", "data"),
    )

    # Layout
    app.layout = html.Div(
        [
            dcc.Store(id="video-start-time"),  # Declare globally in layout
            dcc.Store(id="mouse-data-loaded"),
            dcc.Store(id="selected-day"),
            dcc.Tabs(
                [
                    # dash.dcc.Tab(label='Compare mice', children=[
                    #     dash.dcc.Checklist(
                    #         id='mice-checklist',
                    #         options=[{'label': key, 'value': key} for key in mouse_data_dict.keys()],
                    #         value=[],
                    #         labelStyle={'display': 'block'}
                    #     ),
                    #     dash.dcc.Graph(id='graph')
                    # ]),
                    dcc.Tab(
                        label="Training Village Behavior Explorer",
                        children=[
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dcc.Dropdown(
                                                id="projects-dropdown",
                                                options=[{"label": p, "value": p} for p in projects_list],
                                                value=None,
                                                placeholder="Project",
                                            ),
                                            dcc.Dropdown(
                                                id="single-mouse-dropdown",
                                                options=[],
                                                value=None,
                                                placeholder="Mouse",
                                                style={"margin-top": "8px"},
                                            ),
                                            dcc.Loading(html.Div(id="load-status", style={"margin-top": "8px"})),
                                            html.Div(
                                                f"Data: {data_path}" if data_path else "No data folder found",
                                                style={
                                                    "margin-top": "8px",
                                                    "font-size": "11px",
                                                    "color": "grey",
                                                    "word-break": "break-all",
                                                },
                                            ),
                                        ],
                                        style={"width": "12%", "min-width": "150px", "flex-shrink": "0"},
                                    ),
                                    dcc.Graph(
                                        id="reactive-calendar",
                                        figure=figures.empty_figure("Choose a project and a mouse"),
                                        config={"displayModeBar": False},
                                        style={"flex": "1", "min-width": "0", "height": "230px"},
                                    ),
                                    html.Pre(
                                        id="single-mouse-text",
                                        style={"width": "25%", "flex-shrink": "0", "font-size": "12px", "margin": 0},
                                    ),
                                ],
                                style=ROW,
                            ),
                            html.Div(
                                [
                                    dcc.Graph(id="single-mouse-performance", style={"width": "35%"}),
                                    dcc.Graph(id="single-mouse-psychometric", style={"width": "30%"}),
                                    html.Div(
                                        id="single-mouse-video", style={"width": "35%", "word-break": "break-all"}
                                    ),
                                ],
                                style=ROW,
                            ),
                            dcc.Graph(id="trial-by-trial", figure=figures.empty_figure(), style={"height": "420px"}),
                            html.Div(
                                [
                                    html.Button("Session report", id="session-report-button", style=BUTTON),
                                    html.Button("Training history", id="training-history-button", style=BUTTON),
                                ],
                                style={"margin": "8px 0"},
                            ),
                            dcc.Loading(html.Div(id="session-report")),
                            dcc.Loading(html.Div(id="training-history")),
                        ],
                    ),
                    # dash.dcc.Tab(label='Reports', children=[
                    #     dash.html.H3('Subject progress'),
                    #     dash.dcc.Dropdown(
                    #         id='reports-mice-dropdown',
                    #         options=[{'label': key, 'value': key} for key in mouse_data_dict.keys()],
                    #         value=None,
                    #         multi=False,
                    #         style={'width': '30%'}
                    #     ),
                    #     dash.html.Img(id='subject-progress', src=''),
                    #     dash.html.H3('Session summary'),
                    #     dash.dcc.Dropdown(
                    #         id='reports-session-dropdown',
                    #         options=[{'label': key, 'value': session_data_dict[key]} for key in session_data_dict.keys()],  # noqa: E501
                    #         value=None,
                    #         multi=False,
                    #         style={'width': '30%'}
                    #     ),
                    #     dash.html.Img(id='session-summary', src=''),
                    # ]),
                ]
            ),
        ]
    )

    # The commented-out code (the Compare mice and Reports tabs) used a
    # global mouse_data_dict and old helpers. To bring it back, use instead:
    # data.load_mouse_data(project, mouse) for mouse_data_dict[mouse],
    # figures.matplotlib_to_uri for utils.fig_to_uri, and
    # lecilab_behavior_analysis.figure_maker for fm.

    # @app.callback(
    #     dash.dependencies.Output('graph', 'figure'),
    #     [dash.dependencies.Input('mice-checklist', 'value')],
    # )
    # def update_figure(selected_items):
    #     if len(selected_items) == 0:
    #         return {}
    #     tdfs = []
    #     for key in selected_items:
    #         df = mouse_data_dict[key]
    #         df["mouse_name"] = key
    #         tdfs.append(dft.get_performance_through_trials(df, window=50))
    #     tdf = pd.concat(tdfs)
    #     fig = px.line(tdf, x='total_trial', y='performance_w', color='mouse_name')
    #     return fig

    # the mice of the selected project
    @app.callback(
        dash.Output("single-mouse-dropdown", "options"),
        dash.Output("single-mouse-dropdown", "value"),
        dash.Input("projects-dropdown", "value"),
    )
    def update_mice_options(selected_project):
        mice = data.get_list_of_mice(selected_project)
        return [{"label": mouse, "value": mouse} for mouse in mice], None

    # read the trials of the selected mouse (kept in memory, see data.py)
    @app.callback(
        dash.Output("mouse-data-loaded", "data"),
        dash.Output("load-status", "children"),
        dash.Input("projects-dropdown", "value"),
        dash.Input("single-mouse-dropdown", "value"),
    )
    def update_mouse_data(selected_project, selected_mouse):
        if selected_project is None or selected_mouse is None:
            return None, ""
        try:
            df = data.load_mouse_data(selected_project, selected_mouse)
        except Exception as error:
            return None, f"Could not read the trials: {type(error).__name__}: {error}"
        if df.empty:
            return None, "No trials"
        days = data.trials_per_day(df)
        return (
            {"project": selected_project, "mouse": selected_mouse},
            f"{len(df)} trials in {len(days)} days",
        )

    # the day shown: the last one when a mouse is chosen, then the one clicked
    @app.callback(
        dash.Output("selected-day", "data"),
        dash.Input("mouse-data-loaded", "data"),
        dash.Input("reactive-calendar", "clickData"),
    )
    def update_selected_day(loaded, click_data):
        if not loaded:
            return None
        df = data.load_mouse_data(loaded["project"], loaded["mouse"])
        if dash.ctx.triggered_id == "reactive-calendar" and click_data:
            day = click_data["points"][0].get("customdata")
            if day in data.trials_per_day(df).index:
                return day
            raise PreventUpdate  # a day without trials
        return data.last_day(df)

    @app.callback(
        dash.Output("reactive-calendar", "figure"),
        dash.Output("single-mouse-text", "children"),
        dash.Output("single-mouse-performance", "figure"),
        dash.Output("single-mouse-psychometric", "figure"),
        dash.Output("trial-by-trial", "figure"),
        dash.Output("session-report-button", "children"),
        dash.Output("training-history-button", "children"),
        dash.Input("selected-day", "data"),
        dash.State("mouse-data-loaded", "data"),
    )
    def update_day(day, loaded):
        if not loaded or not day:
            empty = figures.empty_figure()
            return (
                figures.empty_figure("Choose a project and a mouse"),
                "",
                empty,
                empty,
                empty,
                "Session report",
                "Training history",
            )
        df = data.load_mouse_data(loaded["project"], loaded["mouse"])
        day_df = data.day_trials(df, day)
        return (
            figures.calendar_figure(data.trials_per_day(df), selected=day),
            day_text(day_df, loaded["mouse"], day),
            figures.performance_figure(day_df),
            figures.psychometric_figure(day_df),
            figures.trial_by_trial_figure(day_df),
            f"Session report of {day}",
            f"Training history up to {day}",
        )

    # zooming on some trials in the performance or in the trial-by-trial
    # figure zooms on the same trials in the other one, and the psychometric
    # curves are made with the trials in view only
    @app.callback(
        dash.Output("single-mouse-performance", "figure", allow_duplicate=True),
        dash.Output("trial-by-trial", "figure", allow_duplicate=True),
        dash.Output("single-mouse-psychometric", "figure", allow_duplicate=True),
        dash.Input("single-mouse-performance", "relayoutData"),
        dash.Input("trial-by-trial", "relayoutData"),
        dash.State("selected-day", "data"),
        dash.State("mouse-data-loaded", "data"),
        prevent_initial_call=True,
    )
    def sync_zoom(performance_relayout, trials_relayout, day, loaded):
        source = triggered_id()
        zoom = figures.zoom_range(trials_relayout if source == "trial-by-trial" else performance_relayout)
        if zoom is None or not loaded or not day:
            raise PreventUpdate
        return zoom_outputs(
            source, zoom, data.day_trials(data.load_mouse_data(loaded["project"], loaded["mouse"]), day)
        )

    @app.callback(
        dash.Output("single-mouse-video", "children"),
        dash.Output("video-start-time", "data", allow_duplicate=True),
        dash.Input("single-mouse-performance", "clickData"),
        dash.Input("trial-by-trial", "clickData"),
        dash.State("projects-dropdown", "value"),
        prevent_initial_call=True,
    )
    def update_single_mouse_video(performance_click, trial_click, project_name):
        # the trial clicked in either figure (both give the same customdata)
        click_data = trial_click if triggered_id() == "trial-by-trial" else performance_click
        if click_data is None:
            raise PreventUpdate

        try:
            subject, task, session_date, trial = click_data["points"][0]["customdata"]
            video_path = data.video_path(project_name, subject, task, session_date)
        except (KeyError, TypeError, ValueError):
            return html.Div("Invalid click data"), dash.no_update

        if video_path is None or not video_path.exists():
            return html.Div(f"No video of this session: {video_path}"), dash.no_update

        static_video_path = STATIC_PATH / video_path.name
        if not static_video_path.exists():
            try:
                os.symlink(video_path, static_video_path)
            except OSError as e:
                return html.Div(f"Error linking video: {e}"), dash.no_update

        start_time = data.seconds_of_trial(data.load_mouse_data(project_name, subject), session_date, trial)
        video_component = html.Video(
            id="video-player",
            src=f"/videos/{video_path.name}",
            controls=True,
            autoPlay=True,
            muted=True,
            style={"width": "100%"},
        )
        return video_component, {"time": start_time or 0}

    # the figures of the daily report, drawn when their button is clicked
    # (and removed when another day is chosen)
    @app.callback(
        dash.Output("session-report", "children"),
        dash.Input("session-report-button", "n_clicks"),
        dash.Input("selected-day", "data"),
        dash.State("mouse-data-loaded", "data"),
        prevent_initial_call=True,
    )
    def show_session_report(n_clicks, day, loaded):
        if dash.ctx.triggered_id != "session-report-button" or not loaded or not day:
            return None
        df = data.load_mouse_data(loaded["project"], loaded["mouse"])
        return report_image(
            f"{loaded['mouse']}: session report of {day}",
            "session_summary_figure",
            data.day_trials(df, day),
            perf_window=50,
            width=15,
            height=10,
        )

    @app.callback(
        dash.Output("training-history", "children"),
        dash.Input("training-history-button", "n_clicks"),
        dash.Input("selected-day", "data"),
        dash.State("mouse-data-loaded", "data"),
        prevent_initial_call=True,
    )
    def show_training_history(n_clicks, day, loaded):
        if dash.ctx.triggered_id != "training-history-button" or not loaded or not day:
            return None
        df = data.load_mouse_data(loaded["project"], loaded["mouse"])
        try:
            events = data.load_events(loaded["project"])
        except Exception:
            events = None
        return report_image(
            f"{loaded['mouse']}: training history up to {day}",
            "subject_progress_figure",
            data.trials_up_to(df, day),
            perf_window=100,
            summary_matrix_plot=False,
            events_df=events,
        )

    # @app.callback(
    #     dash.dependencies.Output('subject-progress', component_property='src'),
    #     [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    # )
    # def update_subject_progress(selected_value):
    #     if selected_value is None:
    #         return ''
    #     df = mouse_data_dict[selected_value]
    #     fig = fm.subject_progress_figure(df)
    #     return utils.fig_to_uri(fig)

    # @app.callback(
    #     dash.dependencies.Output('reports-session-dropdown', 'options'),
    #     [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    # )
    # def update_session_dropdown(selected_value):
    #     if selected_value is None:
    #         return []
    #     df = mouse_data_dict[selected_value]
    #     session_data_dict = utils.get_diccionary_of_dates(df)
    #     return [{'label': key, 'value': session_data_dict[key]} for key in session_data_dict.keys()]

    # @app.callback(
    #     dash.dependencies.Output('session-summary', component_property='src'),
    #     [dash.dependencies.Input('reports-mice-dropdown', 'value')],
    #     [dash.dependencies.Input('reports-session-dropdown', 'value')],
    # )
    # def update_session_summary(mouse, session):
    #     if mouse is None or session is None:
    #         return ''
    #     df = mouse_data_dict[mouse]
    #     sdf = df[df["year_month_day"] == session]
    #     fig = fm.session_summary_figure(sdf, mouse, perf_window=25)
    #     return utils.fig_to_uri(fig)

    return app


def zoom_outputs(source, zoom, day_df):
    """
    After a zoom on the figure source: the x axis of the other figure (as a
    dash.Patch, the figure that was zoomed is not changed) and the
    psychometric figure of the trials in view.
    """
    patches = {}
    for graph, axes in (("single-mouse-performance", ["xaxis"]), ("trial-by-trial", ["xaxis", "xaxis2"])):
        if graph == source:
            patches[graph] = dash.no_update
            continue
        patch = dash.Patch()
        for axis in axes:
            if zoom == figures.ZOOM_RESET:
                patch["layout"][axis]["autorange"] = True
            else:
                patch["layout"][axis]["range"] = list(zoom)
                patch["layout"][axis]["autorange"] = False
        patches[graph] = patch
    in_view = figures.trials_in_view(day_df, zoom)
    title = None
    if zoom != figures.ZOOM_RESET and len(in_view):
        title = (
            f"trials {int(in_view['total_trial'].min())} to {int(in_view['total_trial'].max())} ({len(in_view)} trials)"
        )
    psychometric = figures.psychometric_figure(in_view, title=title)
    return patches["single-mouse-performance"], patches["trial-by-trial"], psychometric


def triggered_id():
    """The id of the component that triggered the callback (None outside a callback)."""
    try:
        return dash.ctx.triggered_id
    except Exception:
        return None


def day_text(day_df, mouse: str, day: str) -> str:
    """Summary of the trials of a day (as in the daily report)."""
    from lecilab_behavior_analysis.metrics.performance import get_text_from_subset_df

    try:
        return f"{mouse}, {day}\n\n" + get_text_from_subset_df(day_df)
    except Exception as error:
        return f"{mouse}, {day}\n\nCould not summarize the day: {type(error).__name__}: {error}"


def report_image(title: str, figure_name: str, df, **kwargs):
    """A figure of the daily report (lecilab_behavior_analysis.figure_maker) as an image."""
    from lecilab_behavior_analysis import figure_maker

    if df.empty:
        return html.Div(f"{title}: no trials")
    try:
        with REPORT_LOCK:
            fig = getattr(figure_maker, figure_name)(df, **kwargs)
            problems = figures.report_problems(fig)
            src = figures.matplotlib_to_uri(fig)
    except Exception as error:
        return html.Div(f"{title}: could not draw it: {type(error).__name__}: {error}", style={"color": "#c0392b"})
    children = [html.H3(title), html.Img(src=src, style={"max-width": "100%"})]
    if problems:
        children.append(html.Pre("Panels that could not be drawn:\n" + "\n".join(problems), style={"color": "#c0392b"}))
    return html.Div(children)


if __name__ == "__main__":
    app = app_builder()
    app.run(debug=False, port=8050)

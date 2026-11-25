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

Run it with: behavior-explorer (or python behavior_data_visualizer/main.py),
then open http://127.0.0.1:8050. One dashboard can be used by several people
at the same time; http://127.0.0.1:8050/status shows its version and the data
in memory. See behavior-explorer --help for the options.
The data is read from the folder of lecilab_behavior_analysis (the
LECILAB_DATA_PATH environment variable, or the folder of this computer).
"""

import argparse
import datetime
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import List, Optional

if __name__ == "__main__" and not __package__:
    # run as a script (python .../main.py): use the package of this folder,
    # not another copy that may be installed in this python
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dash  # noqa: E402
from dash import dcc, html  # noqa: E402
from dash.exceptions import PreventUpdate  # noqa: E402
from flask import Response, abort, send_from_directory  # noqa: E402

from behavior_data_visualizer import data, figures  # noqa: E402

HOST = "127.0.0.1"  # only reachable from this computer (through an ssh tunnel from others)
PORT = 8050
THREADS = 8  # requests served at the same time (several people, several figures each)
STARTED = datetime.datetime.now()
CODE_FOLDER = Path(__file__).resolve().parents[1]

# matplotlib is not thread safe: one report figure at a time
REPORT_LOCK = threading.Lock()

ROW = {"display": "flex", "flex-direction": "row", "gap": "8px", "align-items": "flex-start"}
SMALL_TEXT = {"margin-top": "8px", "font-size": "11px", "color": "grey", "word-break": "break-all"}
BUTTON = {"margin-right": "8px", "padding": "6px 12px", "cursor": "pointer"}
SETTINGS_TEXT_ROW = {"display": "flex", "flex-wrap": "wrap", "gap": "16px", "align-items": "flex-start"}
SETTINGS_TEXT = {"font-size": "11px", "margin": 0, "max-height": "420px", "overflow": "auto"}
# settings shown above the matrix when a mouse is chosen (those it has)
DEFAULT_SETTINGS = (
    "current_training_stage",
    "punishment",
    "hard_trials_on",
    "reward_amount_ul",
    "reward_amount_ml",
    "holding_response_time",
)


def app_builder():
    # get the list of the projects
    projects_list = data.get_list_of_projects()
    data_path = data.get_data_path()

    app = dash.Dash(__name__, title="Behavior Explorer")

    @app.server.route("/status")
    def status():
        return Response(status_text(), mimetype="text/plain")

    # the videos are sent from the data folder (nothing is written, so any
    # user who can read the data can watch them)
    @app.server.route("/videos/<project>/<mouse>/<filename>")
    def serve_video(project, mouse, filename):
        folder = data.video_folder(project, mouse)
        if folder is None:
            abort(404)
        return send_from_directory(folder, filename)

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
                                    html.Button("Settings history", id="settings-button", style=BUTTON),
                                ],
                                style={"margin": "8px 0"},
                            ),
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id="settings-dropdown",
                                        options=[],
                                        value=[],
                                        multi=True,
                                        placeholder="Settings to show above the matrix",
                                    ),
                                    dcc.Loading(dcc.Graph(id="settings-matrix", figure=figures.empty_figure())),
                                    html.Div(id="session-settings", style=SETTINGS_TEXT_ROW),
                                ],
                                id="settings-section",
                                style={"display": "none"},
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
        dash.Input("settings-matrix", "clickData"),
    )
    def update_selected_day(loaded, click_data, matrix_click=None):
        if not loaded:
            return None
        df = data.load_mouse_data(loaded["project"], loaded["mouse"])
        source = triggered_id()
        if source in ("reactive-calendar", "settings-matrix"):
            clicked = click_data if source == "reactive-calendar" else matrix_click
            day = str((clicked or {"points": [{}]})["points"][0].get("customdata") or "")[:10]
            if day in data.trials_per_day(df).index:
                return day
            raise PreventUpdate  # a day without trials
        return data.last_day(df)

    # the settings history: shown with its button
    @app.callback(
        dash.Output("settings-section", "style"),
        dash.Input("settings-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_settings(n_clicks):
        return {"display": "block"} if n_clicks and n_clicks % 2 == 1 else {"display": "none"}

    # the settings of the mouse (those that change first) and the ones shown by default
    @app.callback(
        dash.Output("settings-dropdown", "options"),
        dash.Output("settings-dropdown", "value"),
        dash.Input("mouse-data-loaded", "data"),
    )
    def update_settings_options(loaded):
        if not loaded:
            return [], []
        return settings_options(data.load_session_settings(loaded["project"], loaded["mouse"]))

    @app.callback(
        dash.Output("settings-matrix", "figure"),
        dash.Output("session-settings", "children"),
        dash.Input("selected-day", "data"),
        dash.Input("settings-dropdown", "value"),
        dash.Input("settings-section", "style"),
        dash.State("mouse-data-loaded", "data"),
    )
    def update_settings_history(day, names, section_style, loaded):
        if not section_style or section_style.get("display") == "none":
            raise PreventUpdate  # hidden: nothing to draw
        if not loaded:
            return figures.empty_figure("Choose a project and a mouse"), None
        df = data.load_mouse_data(loaded["project"], loaded["mouse"])
        table = data.load_session_settings(loaded["project"], loaded["mouse"])
        figure = figures.training_matrix_figure(df, table, list(names or []), day)
        return figure, day_settings_text(table, loaded["mouse"], day)

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

        start_time = data.seconds_of_trial(data.load_mouse_data(project_name, subject), session_date, trial)
        video_component = html.Video(
            id="video-player",
            src=f"/videos/{project_name}/{subject}/{video_path.name}",
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


def settings_options(table) -> tuple:
    """Options of the settings dropdown (those that change first, marked) and the ones shown by default."""
    from lecilab_behavior_analysis.io.settings import SESSION_COLUMNS, changing_settings

    if table.empty:
        return [], []
    changing = changing_settings(table)
    others = sorted(c for c in table.columns if c not in SESSION_COLUMNS and c not in changing)
    options = [{"label": f"{name} (changes)", "value": name} for name in changing] + [
        {"label": name, "value": name} for name in others
    ]
    default = [name for name in DEFAULT_SETTINGS if name in table.columns]
    return options, default


def day_settings_text(table, mouse: str, day):
    """The settings of each session of a day, the changes since the previous session first."""
    from lecilab_behavior_analysis.io.settings import format_session_settings, row_settings

    if table.empty or not day:
        return html.Div("No settings saved for this mouse (sessions_summary.csv).", style=SMALL_TEXT)
    rows = table.reset_index(drop=True)
    on_day = rows[rows["date"].dt.strftime("%Y-%m-%d") == day]
    if on_day.empty:
        return html.Div(f"No settings saved for the sessions of {day}.", style=SMALL_TEXT)
    blocks = []
    for index, row in on_day.iterrows():
        settings = row_settings(row)
        previous = row_settings(rows.loc[index - 1]) if index > 0 else None
        title = f"{mouse}, session of {row['date']:%Y-%m-%d %H:%M} ({row.get('task', '')})"
        blocks.append(html.Pre(format_session_settings(settings, previous, title=title), style=SETTINGS_TEXT))
    return blocks


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


def code_version() -> str:
    """Commit of the code that is running (or the package version if it is not a git clone)."""
    try:

        def git(*args: str) -> str:
            command = ["git", "-C", str(CODE_FOLDER), *args]
            return subprocess.run(command, capture_output=True, text=True, timeout=5, check=True).stdout.strip()

        commit = git("log", "-1", "--format=%h (%cs) %s")
        changed = git("status", "--porcelain", "--untracked-files=no")
        return commit + (" + changes not committed" if changed else "")
    except Exception:
        from behavior_data_visualizer import __version__

        return __version__


VERSION = code_version()  # read once: the code that was loaded when the dashboard started


def status_text() -> str:
    """What is running: to check that a dashboard has the latest code and how much memory it uses."""
    lines = [
        "Behavior Explorer",
        f"code: {VERSION}",
        f"code folder: {CODE_FOLDER}",
        f"python: {sys.executable}",
        f"running since: {STARTED:%Y-%m-%d %H:%M}",
        f"data folder: {data.get_data_path()}",
        f"trials in memory: {data.MICE.total_bytes() / 1e9:.1f} of {data.CACHE_GB:g} GB",
        *[f"  {line}" for line in data.MICE.summary()],
    ]
    return "\n".join(lines) + "\n"


def port_is_free(host: str, port: int) -> bool:
    """Whether nothing is listening on the port (as waitress checks it: free right after a restart)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        if sys.platform != "win32":  # on Windows it would also allow a port in use
            # connections that were just closed keep the port for a while
            candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind((host, port))
        except OSError:
            return False
    return True


def main(argv: Optional[List[str]] = None) -> None:
    """Starts the dashboard (the behavior-explorer command)."""
    parser = argparse.ArgumentParser(
        prog="behavior-explorer",
        description="Training Village Behavior Explorer. One dashboard can be used by several people at once.",
    )
    parser.add_argument("--port", type=int, default=PORT, help="port (default: %(default)s)")
    parser.add_argument("--host", default=HOST, help="address to listen on (default: %(default)s, only this computer)")
    parser.add_argument("--threads", type=int, default=THREADS, help="requests served at once (default: %(default)s)")
    parser.add_argument("--dev", action="store_true", help="use the development server of flask (one user)")
    args = parser.parse_args(argv)

    if not port_is_free(args.host, args.port):
        sys.exit(
            f"Port {args.port} is in use. Another dashboard may be running: see "
            f"http://{args.host}:{args.port}/status, or choose another port with --port."
        )
    app = app_builder()
    print(f"Behavior Explorer ({VERSION}): http://{args.host}:{args.port}", flush=True)
    try:
        if args.dev:
            app.run(debug=False, host=args.host, port=args.port)
        else:
            import waitress

            waitress.serve(app.server, host=args.host, port=args.port, threads=args.threads)
    except OSError as error:
        sys.exit(f"Could not start the dashboard on port {args.port}: {error}")


if __name__ == "__main__":
    main()

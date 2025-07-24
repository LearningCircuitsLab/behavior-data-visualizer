import io
import base64
from lecilab_behavior_analysis import utils as ut
from lecilab_behavior_analysis import df_transforms as dft
import plotly.express as px
import socket
import pandas as pd
from pathlib import Path

def set_mouse_data_dict(data_dict):
    global mouse_data_dict
    mouse_data_dict = data_dict

def fig_to_uri(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    # buf.seek(0)
    fig_data = base64.b64encode(buf.getbuffer()).decode("ascii")
    return f'data:image/png;base64,{fig_data}'

def get_dicctionary_of_sessions(df):
    sessions_dict = {}
    for session in df['session'].unique():
        # get the date of each of the session
        date = df[df['session'] == session]['date'].unique()[0]
        key = str(date) + ' - Session: ' + str(session)
        sessions_dict[key] = session
    return sessions_dict

def get_diccionary_of_dates(df):
    dates_dict = {}
    for date in df['year_month_day'].unique():
        key = str(date)
        dates_dict[key] = date
    return dates_dict

def display_click_data(clickData, mouse_name):
    try:
        date = clickData['points'][0]['customdata'][0]
        df = mouse_data_dict[mouse_name]
    except:
        return 'No date selected'
    # select the dataset
    sdf = df[df['year_month_day'] == date]
    return ut.get_text_from_subset_df(sdf)

# # Update the performance figure
# @app.callback(
#     dash.dependencies.Output('single-mouse-performance', 'figure'),
#     [dash.dependencies.Input('reactive-calendar', 'clickData'),
#     dash.dependencies.Input('single-mouse-dropdown', 'value')],
# )
def update_performance_figure(clickData, mouse_name):
    try:
        date = clickData['points'][0]['customdata'][0]
        df = mouse_data_dict[mouse_name]
    except:
        return {}
    # select the dataset
    sdf = df[df['year_month_day'] == date]
    sdf = dft.get_performance_through_trials(sdf, window=50)
    fig = px.line(
        sdf,
        x='total_trial',
        y='performance_w',
        color='current_training_stage',
        hover_data={
            'total_trial': True,
            'performance_w': True,
            'subject': False,
            'task': False,
            'date': True,
            'trial': False,
            })
    # put legend inside the plot
    fig.update_layout(legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1.02,
        xanchor='right',
        x=1
    ))

    return fig


def update_psychometric_figure(clickData, mouse_name):
    try:
        date = clickData['points'][0]['customdata'][0]
        df = mouse_data_dict[mouse_name]
    except:
        return {}
    # select the dataset
    sdf = df[df['year_month_day'] == date]
    pdf = dft.get_performance_by_difficulty(sdf)
    fig = px.scatter(pdf, x='leftward_evidence', y='leftward_choices')
    return fig


def get_data_path():
    hostname = socket.gethostname()
    paths = {
        "headnode": "/archive/training_village/",
        "minibaps": "/archive/training_village/",
        "minibaps2": "/archive/training_village/",
        "tectum": "/mnt/c/Users/HMARTINEZ/LeCiLab/data/behavioral_data/",
    }
    return paths.get(hostname, None)


def display_video(clickData):
    try:
        total_trial = clickData['points'][0]['x']
        print(clickData)
    
    except:
        return {}
    
    return total_trial


def get_video_path(project_name, mouse_name, task, date, trial):
    # get the path to the video
    data_path = get_data_path()
    if data_path is None:
        return None
    # format date to YYYYMMDD_HHMMSS
    date = date.replace('-', '')
    date = date.replace(':', '')
    date = date.replace(' ', '_')
    # video_path = f"{data_path}/{mouse_name}/videos/{mouse_name}_{total_trial}.mp4"
    # return video_path
    return f"{data_path}/{project_name}/videos/{mouse_name}/{mouse_name}_{task}_{date}.mp4"


def get_mouse_data_dict(project_name):
        # Load the data
        outpath = get_data_path() + project_name + "/sessions/"
        # go through the tree and get the data
        mouse_data_dict = {}
        
        # get the animals from the path
        for path in Path(outpath).iterdir():
            # check if the path is a directory
            if path.is_dir():
                # check if the path has a csv file
                if any(path.glob(f'{path.name}.csv')):
                    data = pd.read_csv(path / f'{path.name}.csv', sep=';')
                    # add columns
                    data = dft.add_day_column_to_df(data)
                    # add it to the dictionary
                    mouse_data_dict[path.name] = data
        # sort the dictionary
        mouse_data_dict = dict(sorted(mouse_data_dict.items()))   
        # pass it to utils to make it global
        set_mouse_data_dict(mouse_data_dict)
        # return the data
        return mouse_data_dict


def get_seconds_of_trial(subject, date, trial_number):
    try:
        df = mouse_data_dict[subject]
        session_df = df[df.date == date]
    except:
        return {}
    
    # get the timestamp of the first trial
    start_of_first_trial = session_df.iloc[0].TRIAL_START
    # get the timestamp of the trial
    trial_start = session_df[session_df['trial'] == trial_number].TRIAL_START.values[0]
    # calculate the difference in seconds
    trial_start_seconds = (trial_start - start_of_first_trial)

    return trial_start_seconds
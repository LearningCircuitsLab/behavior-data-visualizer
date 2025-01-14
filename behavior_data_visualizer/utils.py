import io
import base64
from lecilab_behavior_analysis import utils as ut
from lecilab_behavior_analysis import df_transforms as dft
import plotly.express as px

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

def display_click_data(clickData, mouse_name):
    try:
        date = clickData['points'][0]['customdata'][0]
        df = mouse_data_dict[mouse_name]
    except:
        return 'No date selected'
    # select the dataset
    sdf = df[df['date'] == date]
    return ut.get_text_from_df(sdf, mouse_name)

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
    sdf = df[df['date'] == date]
    sdf = dft.get_performance_through_trials(sdf, window=50)
    fig = px.line(sdf, x='total_trial', y='performance_w', color='current_training_stage')
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
    sdf = df[df['date'] == date]
    pdf = dft.get_performance_by_difficulty(sdf)
    fig = px.scatter(pdf, x='leftward_evidence', y='leftward_choices')
    return fig
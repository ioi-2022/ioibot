# dropbox account credentials
access_token  = "sl.BKdHUR9ie8McUIYPrN3Mde0E8xaO4_39_JUbYvmQob5VgYArXqmOVjRG9B7BhgucEvhBzRJBJlkqQxsFtZfcN9d2rTqHxkg4C573Z9laJ6_wLZS9ouNj9OnprcoWCSof39dMwL90V_Y"
refresh_token = "nkJcgIRIb70AAAAAAAAAAbEFnsVZDSF6kP6CpDipdsMecfwnB_IGoFS3jL7-afiI"
app_key       = "62x880o39xba2pd"
app_secret    = "ekoz0sh72h5fa7o"

# required data
team_url      = "https://docs.google.com/spreadsheets/d/1yzW-gbkdU_JOBIRGA6eo0utytEPha8oChDiZ06Jz-dI/export?format=csv&gid=0"
dropbox_url   = "https://docs.google.com/spreadsheets/d/1yzW-gbkdU_JOBIRGA6eo0utytEPha8oChDiZ06Jz-dI/export?format=csv&gid=1654937967"

import dropbox
import pandas as pd
from datetime import datetime

data = pd.read_csv(dropbox_url)
team = pd.read_csv(team_url)
dbx = dropbox.Dropbox(
        access_token, 
        oauth2_refresh_token = refresh_token,
        app_key = app_key, 
        app_secret = app_secret
      )

# close and delete all file requests to prevent duplicate file requests with different IDs
def clear_file_requests():
    file_req_list = dbx.file_requests_list().file_requests
    for file_req in file_req_list:
        dbx.file_requests_update(file_req.id, open = False)

    dbx.file_requests_delete_all_closed()

clear_file_requests()


# current file directory is set to /Uploads/Day {day}/{real_team_code}
# don't forget to change the directory bot_commands.py if the directory is changed.
result = []
def create_file_requests():
    for key, val in data.iterrows():
        real_team_code = val['RealTeamCode']
        team_code = ('IOI' if real_team_code in ['RUS', 'BLR'] else real_team_code)
        country = team.loc[team['Code'] == team_code, 'Name'].values[0]

        row = dict()
        row['RealTeamCode'] = real_team_code

        print(f"Creating file request link for team {real_team_code} ({country}):")
        for day in range(3):
            path = f"/Uploads/Day {day}/{real_team_code}"

            print(f"\tDay {day}: ", end = "")
            try:
                file_req = dbx.file_requests_create(
                                title = f"File upload request for team {team_code} ({country}): Day {day}",
                                destination = path
                                #deadline = dropbox.file_requests.FileRequestDeadline(deadline = datetime.now()) -> untested, no premium account
                                #description = (optional)
                           )
                row[f'Day {day}'] = file_req.url
                print("Success")
            except:
                print("Failed")

        result.append(row)

create_file_requests()

result = pd.DataFrame.from_records(result)
result.to_csv("dropbox_url.csv", index = False)

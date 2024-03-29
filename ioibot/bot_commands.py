import asyncio
import dropbox
from datetime import datetime

from nio import AsyncClient, MatrixRoom, RoomMessageText

from ioibot.chat_functions import react_to_event, send_text_to_room, make_pill
from ioibot.config import Config
from ioibot.storage import Storage

class User():
    def __init__(self, store: Storage, config: Config, username: str):
        self.username = username
        self.config = config
        self.role = "Unknown"

        users = store.leaders
        teams = store.teams

        user = users.loc[self._get_username(users['UserID']) == username, \
                        ['TeamCode', 'RealTeamCode', 'Name', 'Role', 'UserID']]

        if not user.empty:
            country = teams.loc[teams['Code'] == user.iat[0, 0], ['Name']]
            # if the user is not specified in the spreadsheet,
            # or if the country code is not found,
            # assume that the user is unauthorized to use this bot.
            if country.empty:
                self.role = "Unknown"
            else:
                self.team = user.iat[0, 0]
                self.real_team = user.iat[0, 1]
                self.name = user.iat[0, 2]
                self.role = user.iat[0, 3]
                self.country = country.iat[0, 0]

    def is_leader(self):
        return self.is_tc() or self.role in ['Team Leader', 'Deputy Leader']

    def is_tc(self):
        return 'TC' in self.role

    def _get_username(self, name):
        homeserver = self.config.homeserver_url[8:]
        return "@" + name + ":" + homeserver

class Command:
    def __init__(
        self,
        client: AsyncClient,
        store: Storage,
        config: Config,
        command: str,
        room: MatrixRoom,
        event: RoomMessageText,
    ):
        """A command made by a user.

        Args:
            client: The client to communicate to matrix with.

            store: Bot storage.

            config: Bot configuration parameters.

            command: The command and arguments.

            room: The room the command was sent in.

            event: The event describing the command.
        """
        self.client = client
        self.store = store
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]

    async def process(self):
        user = User(self.store, self.config, self.event.sender)
        self.user = user

        if self.user.role == "Unknown":
            await send_text_to_room(
                self.client, self.room.room_id,
                "You are not authorized to use this bot. Please contact HTC for details."
            )
            return

        """Process the command"""
        if self.command.startswith("echo"):
            await self._echo()

        elif self.command.startswith("react"):
            await self._react()

        elif self.command.startswith("help"):
            await self._show_help()

        elif self.command.startswith("info"):
            await self._show_info()

        elif self.command.startswith("poll"):
            if not self.user.is_tc():
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Only HTC can use this command."
                )
                return

            await self._manage_poll()

        elif self.command.startswith("vote"):
            if not self.user.is_leader():
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Only Team Leader and Deputy Leader can use this command."
                )
                return

            if self.user.team == "IOI":
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Sorry, you are not allowed to vote."
                )
                return

            await self._vote()

        elif self.command.startswith("invite"):
            if not self.user.is_tc():
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Only HTC can use this command."
                )
                return

            await self.invite()

        elif self.command.startswith("accounts"):
            if not self.user.is_leader():
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Only Team Leader and Deputy Leader can use this command."
                )
                return

            await self._show_accounts()

        elif self.command.startswith("dropbox"):
            if not self.user.is_leader():
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Only Team Leader and Deputy Leader can use this command."
                )
                return

            await self._get_dropbox()

        elif self.command.startswith("token"):
            if not self.user.is_leader():
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Only Team Leader and Deputy Leader can use this command."
                )
                return

            await self._get_token()

        else:
            await self._unknown_command()

    async def _echo(self):
        """Echo back the command's arguments"""
        response = " ".join(self.args)
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _react(self):
        """Make the bot react to the command message"""
        # React with a start emoji
        reaction = "⭐"
        await react_to_event(
            self.client, self.room.room_id, self.event.event_id, reaction
        )

        # React with some generic text
        reaction = "Some text"
        await react_to_event(
            self.client, self.room.room_id, self.event.event_id, reaction
        )

    async def _show_help(self):
        """Show the help text"""

        text = ""
        text += "Hello, I am IOI 2022 bot. I understand several commands:  \n\n"
        text += "- `info`: shows various team information\n"
        text += "- `accounts`: shows various accounts for your team\n"
        text += "- `dropbox`: shows Dropbox upload links for your team\n"
        text += "- `vote`: casts vote for your team\n"

        await send_text_to_room(self.client, self.room.room_id, text)

    async def _show_info(self):
        """Show team info"""
        if not self.args:
            text = (
                "Usage:  \n\n"
                "`info <3-letter-country-code>|ic|sc|tc`: shows team/IC/SC/TC members  \n\n"
                "Examples:  \n\n"
                "- `info IDN`  \n"
                "- `info ic`  \n"
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        teamcode = self.args[0].upper()
        teams = self.store.teams
        leaders = self.store.leaders

        if teamcode in ['IC', 'SC', 'TC']:
            rolecode = teamcode
            roles = []
            response = ""

            if rolecode == 'IC':
                roles = ['President', 'Chair of IOI / IC Member', 'IC Member', 'Secretary', 'Treasurer']
            if rolecode == 'SC':
                roles = ['ISC Member', 'HSC', 'Invited HSC']
            if rolecode == 'TC':
                roles = ['ITC Member', 'HTC', 'Invited HTC']

            for idx, role in enumerate(roles):
                if idx > 0:
                    response += "  \n  \n"
                response += f"{role}:  \n"
                for index, member in leaders.iterrows():
                    if member['Role'] == role and member['Chair'] == 1:
                        response += f"  \n- {make_pill(member['UserID'], self.config.homeserver_url)} (Chair) | {member['Name']}"
                for index, member in leaders.iterrows():
                    if member['Role'] == role and member['Chair'] != 1:
                        response += f"  \n- {make_pill(member['UserID'], self.config.homeserver_url)} | {member['Name']}"

            await send_text_to_room(self.client, self.room.room_id, response)
            return

        team = teams.loc[(teams['Code'] == teamcode) & (teams['Visible'] == 1)]

        if team.empty:
            text = (
                f"Team {teamcode} not found!"
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        response = f"""Team members from {teamcode}
        ({team.iloc[0]['Name']}):"""

        curteam = leaders.loc[leaders['TeamCode'] == teamcode]

        roles = []
        for index, member in curteam.iterrows():
            role = member['Role']
            userID = member['UserID']
            if role not in roles and role in ['Team Leader', 'Deputy Leader', 'Guest', 'Remote Adjunct (not on site)', 'Invited Observer/Guest'] and exists(userID):
                roles.append(role)

        for role in roles:
            response += f"  \n  \n{role}: \n"
            for index, member in curteam.iterrows():
                if member['Role'] == role and exists(member['UserID']):
                    response += f"  \n- {make_pill(member['UserID'], self.config.homeserver_url)} | {member['Name']}"

        response += "  \n  \nContestants:  \n"
        for index, row in self.store.contestants.iterrows():
            if row['ContestantCode'].startswith(teamcode):
                response += f"  \n- `{row['ContestantCode']}`"
                if row['Online'] == 1:
                    response += " (online)"
                response += f" | {row['FirstName']} {row['LastName']}"

        await send_text_to_room(self.client, self.room.room_id, response)

    async def _manage_poll(self):
        cursor = self.store.vconn.cursor()

        if not self.args:
            text = (
                "Usage:  \n\n"
                '- `poll new "<question>" "<choices-separated-with-/>"`: create new poll  \n'
                '- `poll update <poll-id> "<question>" "<choices-separated-with-/>"`: update existing poll  \n'
                '- `poll list`: show list of created polls  \n'
                '- `poll activate <poll-id>`: activate a poll  \n'
                '- `poll deactivate`: deactivate all polls  \n\n'

                "Examples:  \n\n"
                '- `poll new "Is this a question?" "yes/no/abstain"`  \n'
                '- `poll update 1 "What is 1+1?" "one/two/yes"`  \n'
                '- `poll activate 10`'
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        elif self.args[0].lower() == 'new':
            input_poll = ' '.join(self.args[1:])
            input_poll = input_poll.split('"')[1::2]

            # wrong format: need more arguments, no double quotes, etc.
            if(len(input_poll) < 2):
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Command format is invalid. Send `poll` to see all commands."
                )
                return

            cursor.execute(
                '''INSERT INTO polls (question, choices, active) VALUES (?, ?, 0)''',
                [input_poll[0], input_poll[1]]
            )
            poll_id = cursor.lastrowid

            await send_text_to_room(
                self.client, self.room.room_id,
                f"Poll created with ID {poll_id}.  \n"
            )

        elif self.args[0].lower() == 'update':
            # no id given
            if len(self.args) < 2:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Command format is invalid. Send `poll` to see all commands."
                )
                return

            poll_id = self.args[1]
            try:
                poll_id = int(poll_id)
            except:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Poll ID must be an integer.  \n"
                )
                return

            input_poll = ' '.join(self.args[2:])
            input_poll = input_poll.split('"')[1::2]

            # wrong format: need more arguments, no double quotes, etc.
            if(len(input_poll) < 2):
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Command format is invalid. Send `poll` to see all commands."
                )
                return

            cursor.execute(
                '''UPDATE polls SET question = ?, choices = ? WHERE poll_id = ?''',
                [input_poll[0], input_poll[1], poll_id]
            )
            id_exist = cursor.execute('''SELECT changes()''').fetchall()[0][0]

            if not id_exist:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    f"Poll {poll_id} does not exist.  \n"
                )
                return

            await send_text_to_room(
                self.client, self.room.room_id,
                f"Poll {poll_id} updated.  \n"
            )

        elif self.args[0].lower() == 'list':
            cursor.execute(
                '''SELECT poll_id, question, choices, active FROM polls'''
            )
            poll_list = cursor.fetchall()

            if not poll_list:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "No polls have been created."
                )
                return

            text = ""
            for poll_detail in poll_list:
                text += f"Poll {poll_detail[0]}"
                if poll_detail[3]: # if poll is active
                    text += " (active)"
                text +=  ":  \n"
                text += f'&emsp;&ensp;"{poll_detail[1]}"  \n'

                options = poll_detail[2].split('/')
                options = '/'.join(("`"+option+"`") for option in options)
                text += f"&emsp;&ensp;{options}  \n\n"

            await send_text_to_room(self.client, self.room.room_id, text)

        elif self.args[0].lower() == 'activate':
            # no id given
            if len(self.args) < 2:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Command format is invalid. Send `poll` to see all commands."
                )
                return

            poll_id = self.args[1]
            try:
                poll_id = int(poll_id)
            except:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    "Poll ID must be an integer.  \n"
                )
                return

            cursor.execute(
                '''SELECT poll_id FROM polls WHERE poll_id = ?''',
                [poll_id]
            )
            id_exist = cursor.fetchall()

            if not id_exist:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    f"Poll {poll_id} does not exist.  \n"
                )
                return

            cursor.execute(
                '''SELECT poll_id FROM polls WHERE active = 1'''
            )
            active_exist = cursor.fetchall()

            if active_exist:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    f"Poll {active_exist[0][0]} is already active. Only one poll can be active at any time.  \n"
                )
                return

            cursor.execute(
                '''UPDATE polls SET active = 1 WHERE poll_id = ?''',
                [poll_id]
            )

            cursor.execute(
                '''SELECT question, choices FROM polls WHERE poll_id = ?''',
                [poll_id]
            )
            active_poll = cursor.fetchall()

            options = active_poll[0][1].split('/')
            options = '/'.join(("`"+option+"`") for option in options)

            text = (
                f"Active poll is now poll {poll_id}:  \n"
                f'&emsp;&ensp;"{active_poll[0][0]}"  \n'
                f"&emsp;&ensp;{options}  \n"
            )
            await send_text_to_room(self.client, self.room.room_id, text)

        elif self.args[0] == 'deactivate':
            cursor.execute(
                '''UPDATE polls SET active = 0 WHERE active = 1'''
            )

            await send_text_to_room(
                self.client, self.room.room_id,
                "All polls deactivated.  \n"
            )

        else:
            await send_text_to_room(
                self.client, self.room.room_id,
                "Unknown command. Send `poll` to see all available commands.  \n"
            )

    async def _vote(self):
        cursor = self.store.vconn.cursor()

        cursor.execute(
            '''SELECT poll_id, question, choices FROM polls WHERE active = 1'''
        )
        active_poll = cursor.fetchall()

        if not active_poll:
            await send_text_to_room(
                self.client, self.room.room_id,
                "There is no active poll to vote!  \n"
            )
            return

        active_poll = active_poll[0]
        poll_id  = active_poll[0]
        question = active_poll[1]
        choices  = active_poll[2].split('/')

        if not self.args:
            text  = f'Question: "{question}"  \n\n'
            text += f"You are voting on behalf of the {self.user.country} team.  \n\n"
            text += "Vote by sending one of: \n\n"
            for choice in choices:
                text += f"- `vote {choice}`  \n"

            await send_text_to_room(self.client, self.room.room_id, text)

        elif ' '.join(self.args) in choices:
            self.args = ' '.join(self.args)

            text = (
                f'Question: "{question}"  \n\n'
                f"You voted `{self.args}` on behalf of the {self.user.country} team."
                " Please wait for your vote to be displayed on the screen.  \n\n"
                "You can amend your vote by resending your vote.  \n"

            )
            await send_text_to_room(self.client, self.room.room_id, text)

            cursor.execute(
                '''
                INSERT INTO votes (poll_id, team_code, choice, voted_by, voted_at)
                VALUES (?, ?, ?, ?, datetime("now", "localtime"))
                ON CONFLICT(poll_id, team_code) DO UPDATE
                SET choice = excluded.choice, voted_by = excluded.voted_by, voted_at = datetime("now", "localtime")
                ''',
                [poll_id, self.user.team, self.args, self.user.username]
            )

        else:
            text  = "Your vote is invalid.  \n\n"
            text += "Vote by sending one of:  \n\n"
            for choice in choices:
                text += f"- `vote {choice}`  \n"

            await send_text_to_room(self.client, self.room.room_id, text)

    async def invite(self):
        """Invite all accounts with role to room"""
        if not self.args:
            text = (
                "Usage:"
                "  \n`invite <role> <room id>`: Invite all accounts with role to room"
                "  \n  \nExamples:"
                "  \n- `invite translators !egvUrNsxzCYFUtUmEJ:matrix.ioi2022.id`"
                "  \n- `invite online !egvUrNsxzCYFUtUmEJ:matrix.ioi2022.id`"
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return


        if self.args[0].lower() == 'translators':
            for index, acc in self.store.leaders.iterrows():
                if acc['Matrix Exists'] == 'Y':
                    if ((acc['Role'] == 'Guest' or acc['Role'] == 'Remote Adjunct (not on site)')
                        and acc['Translating'] == 0
                    ):
                        continue

                    await self.client.room_invite(
                        self.args[1],
                        f"@{acc['UserID']}:{self.config.homeserver_url[8:]}"
                    )
                    await asyncio.sleep(0.25)
                    
        elif self.args[0].lower() == 'online':
            online_countries = set()
            for index, acc in self.store.contestants.iterrows():
                if acc['Online'] == 1:
                    online_countries.add(acc['RealTeamCode'])

            leaders = self.store.leaders
            for country in online_countries:
                leader_accounts = leaders[leaders['RealTeamCode'] == country]
                for index, acc in leader_accounts.iterrows():
                    if acc['Matrix Exists'] == 'Y':
                        await self.client.room_invite(
                            self.args[1],
                            f"@{acc['UserID']}:{self.config.homeserver_url[8:]}"
                        )
                        await asyncio.sleep(0.25)

        await send_text_to_room(self.client, self.room.room_id, "Successfully invited!")

    async def _show_accounts(self):
        if not self.args:
            text = (
                "Usage:  \n\n"
                "- `accounts early-practice`: Show accounts for the early practice contest  \n"
                "- `accounts contest`: Show online contestant accounts for the actual practice/contest days  \n"
                "- `accounts translation`: Show team account for translation system  \n"
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        team_code = self.user.team
        team_country = self.user.country

        if self.args[0].lower() == 'contest':
            contestants = self.store.contestants
            real_team_code = self.user.real_team
            accounts = contestants.loc[contestants['RealTeamCode'] == real_team_code]

            if accounts.empty:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    f"No contestant accounts available for team {team_code} ({team_country}). Please contact HTC for details."
                )
                return

            online_accounts = accounts.loc[accounts['Online'] == 1]

            if online_accounts.empty:
                text = f"All contestants of team {team_code} ({team_country}) are participating on-site."
                text += " We do not distribute contestant accounts for on-site contestants."
                await send_text_to_room(self.client, self.room.room_id, text)
                return

            text = f"Online contestant accounts (`username`: `password`) for team {team_code} ({team_country}):  \n\n"
            for index, account in online_accounts.iterrows():
                text += f"- {account['FirstName']} {account['LastName']}  \n"
                text += f"  `{account['ContestantCode']}`: `{account['Password']}`  \n"

            text += "\n\n These accounts are to be used for actual practice and contest days."

            await send_text_to_room(self.client, self.room.room_id, text)


        elif self.args[0].lower() == 'translation':
            translation = self.store.translation_acc
            account = translation.loc[translation['TeamCode'] == team_code]

            if account.empty:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    f"No translation account available for team {team_code} ({team_country}). Please contact HTC for details."
                )
                return

            text  = f"Translation account (`username`: `password`) for team {team_code} ({team_country}): \n\n"
            text += f"`{team_code}`: `{account.iat[0, 1]}` \n\n"

            await send_text_to_room(self.client, self.room.room_id, text)

        elif self.args[0].lower() == 'early-practice':
            testing = self.store.testing_acc
            real_team_code = self.user.real_team
            accounts = testing.loc[testing['RealTeamCode'] == real_team_code]

            if accounts.empty:
                await send_text_to_room(
                    self.client, self.room.room_id,
                    f"No early practice contest accounts available for team {team_code} ({team_country}). Please contact HTC for details."
                )
                return

            text = f"Early practice contest accounts (`username`: `password`) for team {team_code} ({team_country}): \n\n"
            for index, account in accounts.iterrows():
                text += f"- {account['FirstName']} {account['LastName']}  \n"
                text += f"  `{account['ContestantCode']}`: `{account['Password']}`  \n"
            text += "\n\n These accounts are NOT used for actual contest days."

            await send_text_to_room(self.client, self.room.room_id, text)

        else:
            await send_text_to_room(
                self.client, self.room.room_id,
                "Command format is invalid. Send `accounts` to see all commands."
            )

    async def _get_dropbox(self):
        dropbox_link = self.store.dropbox_url
        team_code = self.user.team
        real_team_code = self.user.real_team
        team_country = self.user.country

        # yyyy/mm/dd format
        if(datetime.now() < datetime(2022, 8, 10)):
            day = 0
        elif(datetime.now() < datetime(2022, 8, 12)):
            day = 1
        else:
            day = 2

        url = dropbox_link.loc[dropbox_link['RealTeamCode'] == real_team_code, "Day " + str(day)]
        if url.empty:
            await send_text_to_room(
                self.client, self.room.room_id,
                f"No Dropbox file request link found for team {team_code} ({team_country}). Plase contact HTC for details."
            )
            return
        url = url.values[0]

        text = f"Dropbox upload link for Day {day} for team {team_code} ({team_country}):  \n\n"
        text += url + "  \n\n"

        dbx = self.store.dbx
        try:
            res = dbx.files_list_folder(f"/Uploads/Day {day}/{real_team_code}")
        except Exception as e:
            await send_text_to_room(self.client, self.room.room_id, "No upload folder found.")
            return 

        if not res.entries:
            text += "The folder is empty. Please upload the required files through the link provided above."
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        text += "List of successfully uploaded files:  \n"

        def list_directory(dbx, path, prefix):
            nonlocal text
            res = dbx.files_list_folder(path)
            for entry in res.entries:
                if (isinstance(entry, dropbox.files.FolderMetadata)):
                    list_directory(dbx, path + "/" + entry.name, prefix + entry.name + "/")
                else:
                    text += f"- `{prefix}{entry.name}`  \n"

        list_directory(dbx, f"/Uploads/Day {day}/{real_team_code}", "")

        await send_text_to_room(self.client, self.room.room_id, text)

    async def _get_token(self):
        tokens = self.store.tokens
        token = tokens.loc[tokens['TeamCode'] == self.user.team]

        if token.empty:
            await send_text_to_room(
                self.client, self.room.room_id,
                "There is no token for your team."
            )
        else:
            await send_text_to_room(
                self.client, self.room.room_id,
                f"Token for team {self.user.team}: `{token.iloc[0, 1]}`"
            )

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )


def exists(n):
    return n == n

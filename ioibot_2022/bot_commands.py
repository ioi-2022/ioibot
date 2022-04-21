import pandas
import re

from datetime import datetime

from nio import AsyncClient, MatrixRoom, RoomMessageText

from ioibot_2022.chat_functions import react_to_event, send_text_to_room
from ioibot_2022.config import Config
from ioibot_2022.storage import Storage

class User():
    def __init__(self, store: Storage, username: str):
        self.id = username
        users = store.users
        teams = store.teams

        user = users.loc[self._get_username(users['UserID']) == username,\
                        ['TeamCode', 'Name', 'Role', 'UserID']]

        country = teams.loc[teams['Code'] == user.iat[0, 0], ['Name']]

        if not user.empty:
            self.team    = user.iat[0, 0]
            self.name    = user.iat[0, 1]
            self.role    = user.iat[0, 2]
            self.id      = user.iat[0, 3]
            self.country = country.iat[0, 0]

    def _get_username(self, user_id):
        return "@" + user_id + ":matrix.ioi2022.id"
        
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
        self.args = re.split('\s+', self.command)[1:]
        self.cmd = re.split('\s+', self.command)[0].lower()

    async def process(self):
        user = User(self.store, self.event.sender)
        self.user = user

        """Process the command"""
        if self.cmd == 'echo':
            await self._echo()

        elif self.cmd == 'react':
            await self._react()

        elif self.cmd == 'help':
            await self._show_help()

        elif self.cmd == 'hello' or self.cmd == 'hi':
            await self._show_help()

        elif self.cmd == 'poll':
            if user.role not in ['HTC']:
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    "Only HTC can use this command."
                )
                return

            await self._manage_poll()


        elif self.cmd == 'vote':
            if user.role not in ['Leader', 'Deputy Leader', 'HTC']:
                await send_text_to_room(
                    self.client, 
                    self.room.room_id,
                    "Only Leader and Deputy Leader can use this command."
                )
                return

            await self._vote()

        else:
            await self._unknown_command()

    async def _echo(self):
        """Echo back the command's arguments"""
        response = " ".join(self.args)
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _manage_poll(self):
        cursor = self.store.vconn.cursor()

        if len(self.args) == 0:
            message  = "List of available commands:  \n\n"
            message += '- poll new "&lt;question&gt;" "&lt;choices&gt;"  \n' 
            message += '- poll update &lt;id&gt; "&lt;question&gt;" "&lt;choices&gt;"  \n'
            message += "- poll list  \n"
            message += "- poll activate &lt;id&gt;  \n"
            message += "- poll deactivate  \n"

            await send_text_to_room(
                self.client,
                self.room.room_id,
                message
            )

        elif self.args[0] == 'new':
            input_poll = ' '.join(self.args[1:])
            input_poll = input_poll.split('"')[1::2]

            cursor.execute(
                '''INSERT INTO polls (question, choices, active) VALUES (?, ?, ?)''',
                [input_poll[0], input_poll[1], 0]
            )

            cursor.execute(
                '''SELECT MAX(poll_id) FROM polls'''
            )
            poll_id = cursor.fetchall()[0][0]

            await send_text_to_room(
                self.client,
                self.room.room_id,
                f"Poll created with ID {poll_id}. \n"
            )

        elif self.args[0] == 'update':
            poll_id = self.args[1]
            try:
                poll_id = int(poll_id)
            except:
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    "Poll ID must be an integer. \n"
                )
                return

            input_poll = ' '.join(self.args[2:])
            input_poll = input_poll.split('"')[1::2]

            cursor.execute(
                '''SELECT poll_id FROM polls WHERE poll_id = ?''',
                [poll_id] 
            )
            id_exist = cursor.fetchall()

            if len(id_exist) == 0:
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    "Poll ID does not exist. \n"
                )
            else:
                cursor.execute(
                    '''UPDATE polls SET question = ?, choices = ? WHERE poll_id = ?''',
                    [input_poll[0], input_poll[1], poll_id]
                )

                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    f"Poll {poll_id} updated.  \n"
                )

        elif self.args[0] == 'list':
            cursor.execute(
                '''SELECT poll_id, question, choices FROM polls'''
            )
            poll_list = cursor.fetchall()

            message = ""
            for poll_detail in poll_list:
                message += f"Poll {poll_detail[0]}:  \n"
                message += f'&emsp;&ensp;"{poll_detail[1]}"  \n'
                message += f'&emsp;&ensp;"{poll_detail[2]}"  \n'
                message += "  \n"

            await send_text_to_room(
                self.client,
                self.room.room_id,
                message
            )

        elif self.args[0] == 'activate':
            poll_id = self.args[1]
            try:
                poll_id = int(poll_id)
            except:
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    "Poll ID must be an integer.  \n"
                )
                return

            cursor.execute(
                '''SELECT poll_id FROM polls WHERE poll_id = ?''',
                [poll_id] 
            )
            id_exist = cursor.fetchall()

            if len(id_exist) == 0:
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    "Poll ID does not exist.  \n"
                )
                return

            cursor.execute(
                '''SELECT poll_id FROM polls WHERE active = 1'''
            )
            active_exist = cursor.fetchall()

            if len(active_exist) != 0:
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    f"Poll {active_exist[0][0]} is already active. Only 1 poll can be active at any time.  \n"
                )
                return
            else:
                cursor.execute(
                    '''UPDATE polls SET active = ? WHERE poll_id = ?''',
                    [1, poll_id]
                )

                cursor.execute(
                    '''SELECT question, choices FROM polls WHERE poll_id = ?''',
                    [poll_id]
                )
                poll_selected = cursor.fetchall()

                message = f"Active poll is now poll {poll_id}:  \n"
                message += f'&emsp;&ensp;"{poll_selected[0][0]}"  \n'
                message += f'&emsp;&ensp;"{poll_selected[0][1]}"  \n'
                await send_text_to_room(
                    self.client,
                    self.room.room_id,
                    message
                )

        elif self.args[0] == 'deactivate':
            cursor.execute(
                '''UPDATE polls SET active = 0 WHERE active = 1'''
            )

            await send_text_to_room(
                self.client,
                self.room.room_id,
                "Poll deactivated."
            )

        else:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                "Unknown command."
            )

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
        if not self.args:
            text = (
                "Hello, I am a bot made with matrix-nio! Use `help commands` to view "
                "available commands."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "rules":
            text = "These are the rules!"
        elif topic == "commands":
            text = "Available commands: ..."
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )

    async def _vote(self):
        cursor = self.store.vconn.cursor()
        pollid = 0

        cursor.execute(
            '''SELECT poll_id, question, choices FROM polls WHERE active = 1'''
        )
        poll_selected = cursor.fetchall()[0]

        if len(poll_selected) == 0:
            await send_text_to_room(
                self.client,
                self.room.room_id,
                "There is no active poll to vote!\n\n"
            )
            return

        poll_id  = poll_selected[0]
        question = poll_selected[1]
        options  = poll_selected[2].split('/')

        # `poll` only
        if len(self.args) == 0:
            message  = f"You are voting on behalf of the {self.user.country} team.  \n\n"
            message += f"Question: {question}  \n\n"
            message += "Vote by sending one of:\n\n"
            for option in options:
                message += f"- `vote {option}`  \n"

            await send_text_to_room(
                self.client,
                self.room.room_id,
                message
            )

        elif ' '.join(self.args) in options:
            self.args = ' '.join(self.args)
            message = f"You voted `{self.args}` on behalf of the {self.user.country} team.  \n"
            message += "Please wait for your vote to be displayed on the screen.  \n"
            message += "You can change your vote by resending your vote.  \n"
            
            await send_text_to_room(
                self.client,
                self.room.room_id,
                message
            )

            cursor.execute(
                '''SELECT poll_id FROM votes WHERE poll_id = ? AND team_code = ?''',
                [poll_id, self.user.country]
            )
            vote_exist = cursor.fetchall()

            if len(vote_exist) == 0:
                cursor.execute(
                    '''
                    INSERT INTO votes (poll_id, team_code, choice, voted_by, voted_at) 
                    VALUES (?, ?, ?, ?, datetime("now", "localtime"))
                    ''',
                    [poll_id, self.user.country, self.args, self.user.id]
                )
            else:
                cursor.execute(
                    '''
                    UPDATE votes SET poll_id = ?, 
                                     team_code = ?, 
                                     choice = ?, 
                                     voted_by = ?, 
                                     voted_at = datetime("now", "localtime")
                    ''',
                    [poll_id, self.user.country, self.args, self.user.id]
                )

        else:
            message = "Your vote is invalid.\n\n"
            message += "Vote by sending one of:\n\n"
            for option in options:
                message += f"- `vote {option}`  \n"

            await send_text_to_room(
                self.client,
                self.room.room_id,
                message
            )    
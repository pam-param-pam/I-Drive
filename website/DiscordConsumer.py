from channels_discord import DiscordConsumer

class MyDiscordConsumer(DiscordConsumer):
    def ready(self):
        """
        Optional hook for actions on connection to Discord
        """
        print('You are now connected to discord!')

    def my_custom_message(self):
        """
        Use built-in functions to send basic discord actions
        """
        self.send_action('dm', user_id='SOME_DISCORD_USER_ID', text='your message')
        self.send_action(
            'send_to_channel',
            channel_id='SOME_DISCORD_CHANNEL_ID',
            text='your message'
        )
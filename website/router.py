from channels.routing import ProtocolTypeRouter

from website.DiscordConsumer import MyDiscordConsumer

application = ProtocolTypeRouter({
    'discord': MyDiscordConsumer,
})
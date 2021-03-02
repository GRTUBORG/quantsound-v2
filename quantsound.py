import asyncio
import functools
import itertools
import math
import random
import os
import discord
import youtube_dl

from async_timeout import timeout
from discord.ext import commands
from asyncio import sleep
from discord.utils import get

youtube_dl.utils.bug_reports_message = lambda: ''
yoomoney_url = os.environ.get('yoomoney_url')
qiwi_url = os.environ.get('qiwi_url')
vk_page = os.environ.get('vk_page')
count_servers = os.environ.get('count_servers')
update = os.environ.get('update')
token = os.environ.get('bot_token')
prefix = 'qs!'

bot = commands.Bot(command_prefix = prefix)
bot.remove_command('help')

class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass

help_message = (':radio: **total radio stations:** `13`'
                '\n**• [Europe +](https://europaplus.ru)** (different), \n**• [Radio Energy](https://www.energyfm.ru)** (different), \n**• [West coast](http://the-radio.ru/radio/pvpjamz-west-coast-r637)** (rap), \n**• [CORE RADIO](https://coreradio.ru)** (rock), '
                '\n**• [Phonk](https://101.ru/radio/user/865080)** (memphis rap), \n**• [Record](https://www.radiorecord.ru)** (different),'
                '\n**• [Record Deep](https://www.radiorecord.ru/station/deep)** (deep house), \n**• [Record Pirate Station](https://www.radiorecord.ru)** (drum and bass), \n**• [Record Black Rap](https://www.radiorecord.ru)** (rap), '
                '\n**• [Record Rock](https://www.radiorecord.ru)** (rock), \n**• [Record Trap](https://www.radiorecord.ru)** (trap), \n**• [Record Dubstep](https://www.radiorecord.ru)** (dubstep), \n**• [Record Rave FM](https://www.radiorecord.ru)** (rave)')
ffmpeg_radio = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download = False, process = False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('Не смог найти то, что соответствует твоему запросу... \n`{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Не смог найти то, что соответствует твоему запросу... \n`{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download = False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Не смог "извлечь" `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Не удалось найти ни одного совпадения для: `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data = info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} дн.'.format(days))
        if hours > 0:
            duration.append('{} ч.'.format(hours))
        if minutes > 0:
            duration.append('{} мин.'.format(minutes))
        if seconds > 0:
            duration.append('{} сек.'.format(seconds))

        return ', '.join(duration)


class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = (discord.Embed(title = 'Сейчас играет:',
                               description = '[YOUTUBE 🎬] [{0.source.title}]({0.source.url}) `({0.source.duration})` [{0.requester.mention}]'.format(self),
                               color = 0xbc03ff)
                 .set_thumbnail(url = self.source.thumbnail)
                 .set_footer(text = "supports by quantsound"))

        return embed


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                # следует добавить песню в течение трёх следующих минут,
                # иначе плеер будет удалён из-за ограничений Discord
                try:
                    async with timeout(180):
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return

            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after = self.play_next_song)
            await self.current.source.channel.send(embed = self.current.create_embed())

            await self.next.wait()

    def play_next_song(self, error = None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('Эта команда не может быть использована в личных чатах!.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('Произошла ошибка: {}'.format(str(error)))

    @commands.command(name = 'join', invoke_without_subcommand = True)
    async def _join(self, ctx: commands.Context):

        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()
    
    @commands.command(name = 'help')
    async def _help(self, ctx: commands.Context):
        author = ctx.message.author
        embed = discord.Embed(description = f'**Привет, {author.mention}! Список доступных команд:**\n'
                            f'• `{prefix}help` вызвать текущую команду;\n'
                            f'• `{prefix}play` (синонимы: `{prefix}p`) команда для проигрывания музыки/стримов;\n'
                            f'• `{prefix}radio` команда для проигрывания радио. Список радиостанций доступен по команде: `{prefix}help_radio`;\n'
                            f'• `{prefix}volume` настроить громкость для следующей песни. Аргументы: целое число от 0 до 100;\n'
                            f'• `{prefix}pause` пауза;\n'
                            f'• `{prefix}resume` воспроизведение;\n'
                            f'• `{prefix}stop` полная остановка песен с удалением очереди;\n'
                            f'• `{prefix}summon` перекинуть бота в нужный вам канал;\n'
                            f'• `{prefix}join` идентична `{prefix}play`, не имеет аргументов и просто говорит боту о подключении к вам;\n'
                            f'• `{prefix}leave` кикнуть бота из голосового канала. **Не работает для радио!**\n'
                            f'• `{prefix}leave_radio` кикнуть бота из голосового канала, если включено радио;\n'
                            f'• `{prefix}now` вывести текущую песню;\n'
                            f'• `{prefix}queue` показать всю очередь;\n'
                            f'• `{prefix}skip` переключить песню в очереди на следующую;\n'
                            f'• `{prefix}shuffle` перемешать всю очередь;\n'
                            f'• `{prefix}remove` удалить песню из очереди. Аргументы: номер песни в очереди в виде целого числа;\n'
                            f'• `{prefix}author` вся информация об авторах quantsound;\n'
                            f'• `{prefix}donate` поддержать разработчика quantsound;\n'
                            f'• `{prefix}servers` показать количество серверов на которых установлен бот. Работает только на домашнем сервере.\n\n\n'
                            '[Пригласить quantsound](https://discord.com/oauth2/authorize?client_id=795312210343624724&permissions=8&scope=bot) | [Домашний сервер](https://discord.gg/MFGmBFjgXu) | [Мы на top.gg](https://top.gg/bot/795312210343624724)' , color = 0xbc03ff)
        embed.set_author(name = "Quantsound support", icon_url = "https://bit.ly/39w96yc")
        embed.set_footer(text = "supports by quantsound")
        await ctx.send(embed = embed)
    
    @commands.command(name = 'donate')
    async def _donate(self, ctx: commands.Context):
        author = ctx.message.author
        embed = discord.Embed(description = f"Hi {author.mention}, I'm really glad you stopped by!\n"
                                            'Our bot is free for the Discord community, but our team will be grateful '
                                            'to you for donating absolutely any amount to the further development of **quantsound**\n\n'
                                            'Payment is available on several e-wallets:\n'
                                            f'• [QIWI]({qiwi_url}),\n'
                                            f'• [ЮMoney]({yoomoney_url}),\n\n'
                                            '*Paypal* and *Webmoney* will also be available soon...\n\n'
                                            'Thank you for choosing us! \n🤍', color = 0xbc03ff)
        embed.set_author(name = "The donations page", icon_url = "https://bit.ly/39w96yc")
        embed.set_footer(text = "supports by quantsound")
        await ctx.send(embed = embed)
    
    @commands.command(name = 'author')
    async def _author(self, ctx: commands.Context):
        embed = discord.Embed(title = 'Our team:', description = f'• Developer: **[Dennis]({vk_page})**,\n'
                                                             '• Developer github: **[GRTUBORG](https://github.com/GRTUBORG)**;\n'
                                                             '• From giving discord member **[•Satoemari•#3381](https://discord.com/users/394850460420538389)**;\n'
                                                             '• Our group in VK: **[quantsound](https://vk.com/quantsound_discord)**.',
                                                             color = 0xbc03ff)
        embed.set_footer(text = "supports by quantsound")
        await ctx.send(embed = embed)
    
    @commands.command(name = 'help_radio')
    async def _help_radio(self, ctx: commands.Context):
        embed = discord.Embed(title = 'List of available radio stations', description = help_message)
        embed.set_footer(text = "supports by quantsound")
        message = await ctx.send(embed = embed)
        await asyncio.sleep(45)
        await message.delete()
    
    @commands.command(name = 'radio', aliases = ['r'])
    async def _radio(self, ctx, *, name, volume = 0.6):
        try:
            message = ctx.message
            await message.add_reaction('📻')
        except:
            None

        name = name.lower()
        author = ctx.message.author

        if name == 'европа +' or name == 'europe +' or name == 'европа плюс' or name == 'europe plus':
            source = 'http://ep128.streamr.ru'
            url = 'https://bit.ly/39gx54n'
            embed = discord.Embed(description = f'Now playing: [Europe +](https://europaplus.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)

        elif name == 'phonk' or name == 'фонк' or name == 'radio phonk':
            source = 'https://bit.ly/3oMtrF7'
            url = 'https://bit.ly/39O1QPw'
            embed = discord.Embed(description = f'Now playing: [Phonk](https://101.ru/radio/user/865080) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
            
        elif name == 'радио рекорд' or name == 'radio record' or name == 'радио record' or name == 'record':
            source = 'http://air2.radiorecord.ru:805/rr_320'
            url = 'https://i.ibb.co/7NjgCS7/record-image.png'
            embed = discord.Embed(description = f'Now playing: [Radio Record](https://www.radiorecord.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)

        elif name == 'record deep' or name == 'deep' or name == 'радио deep' or name == 'radio deep':
            source = 'http://air2.radiorecord.ru:805/deep_320'
            url = 'https://i.ibb.co/bm0kLDc/deep.png'
            embed = discord.Embed(description = f'Now playing: [Record Deep](https://www.radiorecord.ru/station/deep) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)

        elif name == 'radio energy' or name == 'energy' or name == 'энерджи' or name == 'радио энерджи':
            source = 'https://pub0302.101.ru:8443/stream/air/aac/64/99'
            url = 'https://bit.ly/2JXXUlg'
            embed = discord.Embed(description = f'Now playing: [Radio Energy](https://www.energyfm.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)

        elif name == 'radio west' or name == 'west coast' or name == 'радио вест коаст' or name == 'вест коаст':
            source = 'https://stream.pvpjamz.com/stream'
            url = 'https://bit.ly/2LEv9L6' 
            embed = discord.Embed(description = f'Now playing: [Weat Coast](http://the-radio.ru/radio/pvpjamz-west-coast-r637) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
        
        elif name == 'pirate station' or name == 'dnb' or name == 'record pirate station' or name == 'пиратская станция':
            source = 'https://air.radiorecord.ru:805/ps_128'
            url = 'https://i.ibb.co/x1NMzxH/pirate-station.png'
            embed = discord.Embed(description = f'Now playing: [Record Pirate Station](https://www.radiorecord.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
        
        elif name == 'black rap' or name == 'rap' or name == 'record black rap':
            source = 'https://air.radiorecord.ru:805/yo_128'
            url = 'https://i.ibb.co/bPN6R49/black-rap.png'
            embed = discord.Embed(description = f'Now playing: [Record Black Rap](https://www.radiorecord.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
            
        elif name == 'trap' or name == 'record trap':
            source = 'https://air.radiorecord.ru:805/trap_128'
            url = 'https://i.ibb.co/f0DGsG2/trap.png' 
            embed = discord.Embed(description = f'Now playing: [Record Trap](https://www.radiorecord.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
            
        elif name == 'rock' or name == 'record rock':
            source = 'https://air.radiorecord.ru:805/rock_128'
            url = 'https://i.ibb.co/JWLVFTz/rock.png'
            embed = discord.Embed(description = f'Now playing: [Record Rock](https://www.radiorecord.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
            
        elif name == 'dubstep' or name == 'record dubstep':
            source = 'https://air.radiorecord.ru:805/dub_128'
            url = 'https://i.ibb.co/kmqtvn3/dubstep.png'
            embed = discord.Embed(description = f'Now playing: [Record Dubstep](https://www.radiorecord.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
        
        elif name == 'core' or name == 'core radio':
            source = 'https://music.coreradio.ru/radio'
            url = 'https://bit.ly/2O6UcYk'
            embed = discord.Embed(description = f'Now playing: [CORE RADIO](https://coreradio.ru) [{author.mention}] \n\n⚠️ At this radio, the stream freezes a little at the very beginning, I advise you to wait 15 seconds...', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
            
        elif name == 'dnb classic' or name == 'record dnb classic':
            source = 'https://air.radiorecord.ru:805/drumhits_128' 
            url = 'https://i.ibb.co/PZTPFyd/dnb-classic-icon.png'
            embed = discord.Embed(description = f'Now playing: [CORE RADIO](https://coreradio.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
        
        elif name == 'rave' or name == 'rave fm' or name == 'рейв' or name == 'rave fm':
            source = 'https://air.radiorecord.ru:805/rave_128'
            url = 'https://bit.ly/2YMGc8b'
            embed = discord.Embed(description = f'Now playing: [Record Rave FM](https://coreradio.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)
        
        else:
            message_invalid = await ctx.send('I caught an invalid request, I play the radio station `Europe +`')
            source = 'http://ep128.streamr.ru'
            url = 'https://bit.ly/39gx54n'
            embed = discord.Embed(description = f'Now playing: [Europe +](https://europaplus.ru) [{author.mention}]', color = 0xbc03ff)
            embed.set_author(name = 'Radio', icon_url = url)
            embed.set_footer(text = "supports by quantsound")
            await ctx.send(embed = embed)

        voice_channel = ctx.message.author.voice.channel
        vc = await voice_channel.connect(reconnect = True)

        vc.play(discord.FFmpegPCMAudio(executable = "/app/vendor/ffmpeg/ffmpeg", source = source, **ffmpeg_radio))
        vc.source = discord.PCMVolumeTransformer(vc.source)
        vc.source.volume = volume
        
    @commands.command(name = 'leave_radio')
    async def _leave_radio(self, ctx):
        author = ctx.message.author
        try:
            voice_channel = ctx.message.author.voice.channel
            voice = get(bot.voice_clients, guild = ctx.guild)
        except:
            message = await ctx.send(f"{author.mention}, вы не подключены к голосовому каналу!")
            await asyncio.sleep(5)
            await message.delete()
            
        if voice:
            try:
                message = ctx.message
                await message.add_reaction('👋')
            except:
                None
                
            await ctx.voice_client.disconnect()
        else:
            message = await ctx.send("Я не подключен к каналу!")
            await asyncio.sleep(5)
            await message.delete()    
    
    @commands.command(name = 'servers')
    async def _servers(self, ctx: commands.Context):
        if ctx.guild.id == 526097247285280768:
            servers = bot.guilds
            await ctx.send(f'Бот установлен на {len(servers)} серверах')
        else:
            message = await ctx.send("У вас нет доступа к этой команде! \nПерейдите на домашний сервер бота, чтобы использовать данную команду!")
            await asyncio.sleep(5) 
            await message.delete()
            
    @commands.command(name = 'summon')
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):

        if not channel and not ctx.author.voice:
            raise VoiceError('Вы не подключены к голосовому каналу и/или не указали канал для подключения.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name = 'leave', aliases = ['disconnect'])
    async def _leave(self, ctx: commands.Context):

        if not ctx.voice_state.voice:
            return await ctx.send('Вы не подключены ни к одному голосовому каналу.')

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name = 'volume')
    async def _volume(self, ctx: commands.Context, *, volume: int):

        if not ctx.voice_state.is_playing:
            return await ctx.send('В данный момент ничего не проигрывается.')

        if 0 > volume > 100:
            return await ctx.send('Громкость должна быть в пределах от 0 до 100')

        ctx.voice_state.volume = volume / 100
        await ctx.send('Громкость плеера установлена на {}%'.format(volume))

    @commands.command(name = 'now', aliases = ['current', 'playing'])
    async def _now(self, ctx: commands.Context):

        await ctx.send(embed = ctx.voice_state.current.create_embed())

    @commands.command(name = 'pause')
    async def _pause(self, ctx: commands.Context):

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name = 'resume')
    async def _resume(self, ctx: commands.Context):

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name = 'stop')
    async def _stop(self, ctx: commands.Context):

        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name = 'skip')
    async def _skip(self, ctx: commands.Context):

        if not ctx.voice_state.is_playing:
            return await ctx.send('Сейчас никакая музыка не проигрывается...')
        
        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 3:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                await ctx.send('Пропуск песни по голосованию добавлен, голосов: **{}/3**'.format(total_votes))

        else:
            await ctx.send('Вы уже проголосовали за то, чтобы пропустить эту песню.')

    @commands.command(name = 'queue', aliases = ['q'])
    async def _queue(self, ctx: commands.Context, *, page: int = 1):

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Очередь пуста.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start = start):
            queue += '`{0})` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description = '**Всего в очереди: {}**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text = 'Страница {}/{}'.format(page, pages)))
        await ctx.send(embed = embed)

    @commands.command(name = 'shuffle')
    async def _shuffle(self, ctx: commands.Context):

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Очередь пуста.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name = 'remove')
    async def _remove(self, ctx: commands.Context, index: int):

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Очередь пуста. Удалять нечего.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name = 'play', aliases = ['p'])
    async def _play(self, ctx: commands.Context, *, search: str):

        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop = self.bot.loop)
            except YTDLError as e:
                await ctx.send('При обработке этого запроса произошла ошибка: {}. Повторите через несколько секунд!'.format(str(e)))
            else:
                
                song = Song(source)
                if len(ctx.voice_state.songs) == 0:
                    await ctx.voice_state.songs.put(song)
                else:
                    await ctx.voice_state.songs.put(song)
                    await ctx.send('Добавил в очередь: {}'.format(str(source)))

    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('Вы не подключены ни к одному голосовому каналу.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Бот уже находится в голосовом канале.')

bot.add_cog(Music(bot))

@bot.event
async def on_ready():
    print('{0.user} в онлайне!'.format(bot))
    while True:
        await bot.change_presence(status = discord.Status.idle, activity = discord.Activity(type = discord.ActivityType.listening, name = f"{prefix}help 🎶"))
        await sleep(30)
        await bot.change_presence(status = discord.Status.idle, activity = discord.Activity(type = discord.ActivityType.listening, name = f"latest update: {update}"))
        await sleep(5)
        await bot.change_presence(status = discord.Status.idle, activity = discord.Activity(type = discord.ActivityType.listening, name = f"{count_servers} servers!"))
        await sleep(5)

bot.run(str(token))

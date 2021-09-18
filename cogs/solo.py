import discord
import os
import traceback

from humanfriendly import format_timespan as timeez

from discord.ext import commands
from discord.ext.commands import cooldown, BucketType

from data import dbconn
from utils import cf_api, discord_, codeforces, updation
from constants import AUTO_UPDATE_TIME


LOWER_RATING = 800
UPPER_RATING = 3600
MAX_TAGS = 5
MAX_ALTS = 5


class Solo(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.cf = cf_api.CodeforcesAPI()

    def make_solo_embed(self, ctx):
        desc = "Information about Solo Levelling commands! **[use ;solo <command>]**\n\n"
        x = self.client.get_command('solo')

        for cmd in x.commands:
            desc += f"`{cmd.name}`: **{cmd.brief}**\n"
        embed = discord.Embed(description=desc, color=discord.Color.dark_magenta())
        embed.set_author(name="Lockout commands help", icon_url=ctx.me.avatar_url)
        embed.set_footer(
            text="Use the prefix ; before each command. For detailed usage about a particular command, type ;help "
                 "solo <command>")
        return embed

    @commands.group(brief='Commands for single player! Type ;solo for more details', invoke_without_command=True)
    async def solo(self, ctx):
        await ctx.send(embed=self.make_solo_embed(ctx))

    @solo.command(name="arise", brief="Begin solo levelling")
    async def arise(self, ctx):
        user = ctx.author

        if self.db.in_a_solo(ctx.guild.id, user.id):
            await discord_.send_message(ctx, f"{user.mention} finish you current solo first, or if you give up use "
                                             f"`;solo loser`")
            return

        if not self.db.get_handle(ctx.guild.id, user.id):
            await discord_.send_message(ctx, f"Handle for {user.mention} not set! Use `;handle identify` to register")
            return

        if self.db.in_queue(ctx.guild.id, user.id):
            await discord_.send_message(ctx, f"{user.mention} bruv pls dont use it again")
            return
        self.db.add_to_queue(ctx.guild.id, user.id)

        try:
            rating = await discord_.get_seq_response(self.client, ctx, f"{user.mention} enter the rating of problem "
                                                                       f"(between {LOWER_RATING} and {UPPER_RATING})",
                                                     60, 1, user, [LOWER_RATING, UPPER_RATING])
            if not rating[0]:
                await discord_.send_message(ctx, f"{user.mention} you took too long to decide")
                return
            rating = rating[1]

            tags = await discord_.get_tag_response(self.client, ctx, f"{user.mention} Do you want to specify any tags? "
                                                                     f"Type none if not applicable else type"
                                                                     f"`tag 1, tag 2, tag 3 ...` You can add upto **"
                                                                     f"{MAX_TAGS}** tags", MAX_TAGS, 60, user)
            if not tags[0]:
                await discord_.send_message(ctx, f"{user.mention} you took too long to decide")
                return
            tags = tags[1]

            alts = await discord_.get_alt_response(self.client, ctx, f"{user.mention} Do you want to add any alts? "
                                                                     f"Type none if not applicable else type `alts: "
                                                                     f"handle_1 handle_2 ...` You can add upto **"
                                                                     f"{MAX_ALTS}** alt(s)", MAX_ALTS, 60, user)

            if not alts:
                await discord_.send_message(ctx, f"{user.mention} you took too long to decide")
                return

            alts = alts[1]

            await ctx.send(embed=discord.Embed(description="Starting...", color=discord.Color.green()))

            problems = await codeforces.find_problems([self.db.get_handle(ctx.guild.id, user.id)]+alts, rating, tags)
            if not problems[0]:
                await discord_.send_message(ctx, problems[1])
                return

            problems = problems[1]

            self.db.add_to_ongoing_solo(ctx, user, problems[0], rating[0], tags, alts, False)
            solo_info = self.db.get_solo_info(ctx.guild.id, user.id)

            await ctx.send(embed=discord_.solo_embed(solo_info, user))
        finally:
            self.db.remove_from_queue(ctx.guild.id, user.id)

    @solo.command(name="doing", brief="When you know what you want to solve but are addicted to solo")
    async def doing(self, ctx):
        user = ctx.author

        if self.db.in_a_solo(ctx.guild.id, user.id):
            await discord_.send_message(ctx, f"{user.mention} finish you current solo first, or if you give up use "
                                             f"`;solo loser`")
            return

        if not self.db.get_handle(ctx.guild.id, user.id):
            await discord_.send_message(ctx, f"Handle for {user.mention} not set! Use `;handle identify` to register")
            return

        if self.db.in_queue(ctx.guild.id, user.id):
            await discord_.send_message(ctx, f"{user.mention} bruv pls dont use it again")
            return
        self.db.add_to_queue(ctx.guild.id, user.id)

        try:
            ids = await discord_.get_problems_response(self.client, ctx,
                                                       f"{ctx.author.mention} enter problem id denoting the problem. "
                                                       f"Eg: `123/A`",
                                                       60, 1, ctx.author)
            if not ids[0]:
                await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
                return

            problem = ids[1][0]

            await ctx.send(embed=discord.Embed(description="Starting...", color=discord.Color.green()))

            redo = await codeforces.check_solved([self.db.get_handle(ctx.guild.id, user.id)], problem.id, problem.index)
            self.db.add_to_ongoing_solo(ctx, user, problem, problem.rating, problem.tags.split(','), [], redo)
            solo_info = self.db.get_solo_info(ctx.guild.id, user.id)

            await ctx.send(embed=discord_.solo_embed(solo_info, user))
        finally:
            self.db.remove_from_queue(ctx.guild.id, user.id)

    @solo.command(brief="Update solo status for the server")
    @cooldown(1, AUTO_UPDATE_TIME, BucketType.guild)
    async def update(self, ctx):
        await ctx.send(embed=discord.Embed(description="Updating solos for this server", color=discord.Color.green()))
        solos = self.db.get_all_solos(ctx.guild.id)

        for solo in solos:
            try:
                resp = await updation.update_solo(solo)
                if not resp[0]:
                    logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                    await logging_channel.send(f"Error while updating solo: {resp[1]}")
                    continue
                resp = resp[1]
                channel = self.client.get_channel(solo.channel)

                if resp[1]:
                    await channel.send(f"{(await ctx.guild.fetch_member(solo.user)).mention} there is an update")

                if resp[1]:
                    solo_info = self.db.get_solo_info(solo.guild, solo.user)

                    self.db.delete_solo(solo_info.guild, solo_info.user)
                    self.db.add_to_finished_solos(solo_info)
                    if not solo_info.redo:
                        self.db.update_solo_score(solo.guild, solo.user, (solo.rating / 100) ** 2)

                    embed = discord.Embed(color=discord.Color.dark_magenta())
                    embed.add_field(name="User", value=(await ctx.guild.fetch_member(solo.user)).mention)
                    embed.add_field(name="Problem Rating", value=solo_info.rating)
                    embed.add_field(name="Time Taken", value=timeez(solo_info.duration))
                    embed.set_author(name=f"Solo over! Final time")
                    await channel.send(embed=embed)

            except Exception:
                logging_channel = await self.client.fetch_channel(os.environ.get("LOGGING_CHANNEL"))
                await logging_channel.send(f"Error while updating solos: {str(traceback.format_exc())}")

    @solo.command(name="view", brief="View problem(s) of ongoing solo(s)")
    async def view(self, ctx, member: discord.Member = None):
        if not member:
            member = ctx.author
        if not self.db.in_a_solo(ctx.guild.id, member.id):
            await discord_.send_message(ctx, f"{member.mention} is not in a solo")
            return

        solo_info = self.db.get_solo_info(ctx.guild.id, member.id)
        await ctx.send(embed=discord_.solo_embed(solo_info, member))

    @solo.command(brief="Give up like the loser you are")
    async def loser(self, ctx):
        if not self.db.in_a_solo(ctx.guild.id, ctx.author.id):
            await discord_.send_message(ctx, f"{ctx.author.mention} cant lose a solo you never started")
            return
        self.db.delete_solo(ctx.guild.id, ctx.author.id)
        self.db.update_solo_score(ctx.guild.id, ctx.author.id, 0, True)
        await discord_.send_message(ctx, f"{ctx.author.mention} is a loser")

    @solo.command(brief="Check the server leaderboard")
    async def scoreboard(self, ctx):
        res = self.db.get_solo_score(ctx.guild.id)
        res = sorted(res, key=lambda s: s.loss_count)
        res = sorted(res, key=lambda s: s.score, reverse=True)

        desc = "Who is the biggest <:chad:818455088002498560>"
        embed = discord.Embed(description=desc, color=discord.Color.magenta())
        embed.set_author(name="Server Solo Scoreboard")
        embed.add_field(name="User", value='\n'.join(
            [f"{(await ctx.guild.fetch_member(x.user)).mention}" for x in res]))
        embed.add_field(name="Solo Score", value='\n'.join([f"{x.score}" for x in res]))
        embed.add_field(name="Loss Count", value='\n'.join([f"{x.loss_count}" for x in res]))

        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Solo(client))

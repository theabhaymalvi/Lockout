import discord

from discord.ext import commands

from data import dbconn
from utils import cf_api, discord_, codeforces

MAX_PROBLEMS = 20
LOWER_RATING = 800
UPPER_RATING = 3500
MAX_TAGS = 5
MAX_ALTS = 5


class Random(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db = dbconn.DbConn()
        self.cf = cf_api.CodeforcesAPI()

    @commands.command(name="suggest")
    async def suggest(self, ctx, *users: discord.Member):
        users = list(set(users))
        if len(users) == 0:
            await discord_.send_message(ctx, f"The correct usage is `;suggest @user1 @user2...`")
            return
        if ctx.author not in users:
            users.append(ctx.author)
        for i in users:
            if not self.db.get_handle(ctx.guild.id, i.id):
                await discord_.send_message(ctx, f"Handle for {i.mention} not set! Use `;handle identify` to register")
                return

        problem_cnt = await discord_.get_time_response(self.client, ctx,
                                                       f"{ctx.author.mention} enter the number of problems per rating "
                                                       f"between [1, {MAX_PROBLEMS}]",
                                                       30, ctx.author, [1, MAX_PROBLEMS])
        if not problem_cnt[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        problem_cnt = problem_cnt[1]

        rating = await discord_.get_seq_response(self.client, ctx, f"{ctx.author.mention} enter space seperated "
                                                                   f"lowerbound and upperbound ratings of problems ("
                                                                   f"between {LOWER_RATING} and {UPPER_RATING})", 60,
                                                 2, ctx.author, [LOWER_RATING, UPPER_RATING])
        if not rating[0]:
            await discord_.send_message(ctx, f"{ctx.author.mention} you took too long to decide")
            return
        rating = rating[1]

        await ctx.send("Have patience...")

        rs = []
        r = rating[0]
        while r <= rating[1]:
            rs += [r]*problem_cnt
            r += 100
        problems = await codeforces.find_problems([self.db.get_handle(ctx.guild.id, x.id) for x in users], rs)
        if not problems[0]:
            await discord_.send_message(ctx, problems[1])
            return
        problems = problems[1]

        embed = discord.Embed(description=f"{ctx.author.mention} the dice has been rolled", color=discord.Color.magenta())
        embed.set_author(name="Random Mashup")

        embed.add_field(name="Problem", value="\n".join([f"[{p.name}](https://codeforces.com/contest/{p.id}/"
                                                         f"problem/{p.index})" for p in problems]), inline=True)
        embed.add_field(name="Id", value="\n".join([f"{p.id}{p.index}" for p in problems]), inline=True)
        embed.add_field(name="Rating", value="\n".join([f"{p.rating}" for p in problems]), inline=True)

        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Random(client))

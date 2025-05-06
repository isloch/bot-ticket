import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# Para Replit ou hosting online
from keep_alive import keep_alive
keep_alive()

my_secret = os.environ['DISCORD_TOKEN']

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

CONFIG_FILE = 'config.json'
VIPS_FILE = 'vips.json'

# Carrega configurações
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        configs = json.load(f)
else:
    configs = {}

# Carrega VIPs
if os.path.exists(VIPS_FILE):
    with open(VIPS_FILE, 'r') as f:
        vips = json.load(f)
else:
    vips = {}

# Salva configurações
async def salvar_configs():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(configs, f, indent=4)

# Salva VIPs
def salvar_vips():
    with open(VIPS_FILE, 'w') as f:
        json.dump(vips, f, indent=4)

# Sincroniza comandos de barra quando o bot estiver pronto
@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos de barra sincronizados com sucesso.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")
    print(f"Bot logado como {bot.user}.")

@bot.tree.command(name="configpainel")
@app_commands.describe(
    categoria="Categoria onde os tickets serão criados",
    canal_logs="Canal onde logs serão enviados",
    cargos="Cargos que poderão ver os tickets"
)
async def configpainel(interaction: discord.Interaction, categoria: discord.CategoryChannel, canal_logs: discord.TextChannel, cargos: str):
    guild_id = str(interaction.guild_id)

    if str(interaction.user.id) not in vips:
        await interaction.response.send_message("❌ Você não tem acesso a este comando. Use /suporte para mais informações.", ephemeral=True)
        return

    cargo_ids = [int(c.strip().replace('<@&', '').replace('>', '')) for c in cargos.split(',')]

    configs[guild_id] = {
        "categoria_tickets": categoria.id,
        "canal_logs": canal_logs.id,
        "cargos_autorizados": cargo_ids,
        "opcoes": {}
    }

    await salvar_configs()
    await interaction.response.send_message("✅ Painel configurado com sucesso!", ephemeral=True)

@bot.tree.command(name="addcategoria")
@app_commands.describe(nome="Nome da categoria", descricao="Descrição da categoria", emoji="Emoji")
async def addcategoria(interaction: discord.Interaction, nome: str, descricao: str, emoji: str):
    guild_id = str(interaction.guild_id)

    if str(interaction.user.id) not in vips:
        await interaction.response.send_message("❌ Você não tem acesso a este comando.", ephemeral=True)
        return

    if guild_id not in configs:
        await interaction.response.send_message("❌ O painel ainda não foi configurado neste servidor.", ephemeral=True)
        return

    configs[guild_id]["opcoes"][nome] = {
        "emoji": emoji,
        "titulo": nome,
        "descricao": descricao
    }

    await salvar_configs()
    await interaction.response.send_message(f"✅ Categoria '{nome}' adicionada com sucesso!", ephemeral=True)

@bot.tree.command(name="removercategoria")
@app_commands.describe(nome="Nome da categoria")
async def removercategoria(interaction: discord.Interaction, nome: str):
    guild_id = str(interaction.guild_id)

    if str(interaction.user.id) not in vips:
        await interaction.response.send_message("❌ Você não tem acesso a este comando.", ephemeral=True)
        return

    if guild_id not in configs or nome not in configs[guild_id]["opcoes"]:
        await interaction.response.send_message("❌ Categoria não encontrada.", ephemeral=True)
        return

    del configs[guild_id]["opcoes"][nome]
    await salvar_configs()
    await interaction.response.send_message(f"✅ Categoria '{nome}' removida com sucesso!", ephemeral=True)

@bot.tree.command(name="listarcategorias")
async def listarcategorias(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    if guild_id not in configs or not configs[guild_id]["opcoes"]:
        await interaction.response.send_message("❌ Nenhuma categoria configurada.", ephemeral=True)
        return

    categorias = configs[guild_id]["opcoes"]
    texto = "\n".join([f"{v['emoji']} **{v['titulo']}** - {v['descricao']}" for v in categorias.values()])
    await interaction.response.send_message(f"📋 Categorias disponíveis:\n{texto}", ephemeral=True)

class PainelDropdown(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = str(guild_id)
        opcoes = [
            discord.SelectOption(
                label=opc['titulo'],
                description=opc['descricao'],
                emoji=opc['emoji'],
                value=key
            )
            for key, opc in configs[self.guild_id]["opcoes"].items()
        ]
        super().__init__(placeholder="Clique e selecione uma categoria", options=opcoes)

    async def callback(self, interaction: discord.Interaction):
        opcao = self.values[0]
        guild_config = configs[self.guild_id]
        categoria = discord.utils.get(interaction.guild.categories, id=guild_config['categoria_tickets'])

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)
        }

        for cargo_id in guild_config['cargos_autorizados']:
            cargo = interaction.guild.get_role(cargo_id)
            if cargo:
                overwrites[cargo] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        overwrites[interaction.user] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        canal = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}-{opcao}",
            category=categoria,
            overwrites=overwrites
        )

        view = FecharTicket()
        await canal.send(f"🔔 {interaction.user.mention}, a equipe de suporte já está a caminho para atender seu ticket!", view=view)
        await interaction.response.send_message(f"✅ Ticket criado: {canal.mention}", ephemeral=True)

class PainelView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__()
        self.add_item(PainelDropdown(guild_id))

class FecharTicket(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild_id)
        canal_logs_id = configs[guild_id]['canal_logs']
        canal_logs = interaction.guild.get_channel(canal_logs_id)

        await interaction.channel.delete()
        if canal_logs:
            await canal_logs.send(f"📁 Ticket fechado: {interaction.channel.name}")

@bot.tree.command(name="painel")
async def painel_command(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    if str(interaction.user.id) not in vips:
        await interaction.response.send_message("❌ Você não tem acesso a este comando.", ephemeral=True)
        return

    if guild_id not in configs:
        await interaction.response.send_message("❌ O painel ainda não foi configurado neste servidor.", ephemeral=True)
        return

    embed = discord.Embed(title="🎫 Painel de Tickets", description="Selecione a categoria para abrir seu ticket:", color=0x2b2d31)
    view = PainelView(guild_id)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="addvip", description="Adiciona um usuário como VIP")
@app_commands.describe(usuario="Usuário para conceder VIP")
async def addvip(interaction: discord.Interaction, usuario: discord.User):
    if str(interaction.user.id) != "978657917974757459":
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    vips[str(usuario.id)] = True
    salvar_vips()

    membro = interaction.guild.get_member(usuario.id)
    if membro:
        cargo = discord.utils.get(interaction.guild.roles, name="Cliente")
        if cargo:
            await membro.add_roles(cargo)
            await interaction.response.send_message(f"✅ {usuario.mention} agora é VIP e recebeu o cargo **Cliente**!", ephemeral=True)
            return

    await interaction.response.send_message(f"✅ {usuario.mention} foi adicionado como VIP!", ephemeral=True)

@bot.tree.command(name="listavips")
async def listavips(interaction: discord.Interaction):
    if str(interaction.user.id) != "978657917974757459":
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    if not vips:
        await interaction.response.send_message("❌ Não há VIPs cadastrados.", ephemeral=True)
        return

    lista_vips = "\n".join([f"<@{vip_id}>" for vip_id in vips.keys()])
    await interaction.response.send_message(f"📋 Lista de VIPs:\n{lista_vips}", ephemeral=True)

@bot.tree.command(name="removervip", description="Remove um usuário da lista de VIPs")
@app_commands.describe(usuario="Usuário para remover do VIP")
async def removervip(interaction: discord.Interaction, usuario: discord.User):
    if str(interaction.user.id) != "978657917974757459":
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    if str(usuario.id) not in vips:
        await interaction.response.send_message(f"❌ {usuario.mention} não é VIP.", ephemeral=True)
        return

    del vips[str(usuario.id)]
    salvar_vips()
    await interaction.response.send_message(f"✅ {usuario.mention} foi removido dos VIPs.", ephemeral=True)

@bot.tree.command(name="suporte", description="Acesse o servidor de suporte do bot")
async def suporte(interaction: discord.Interaction):
    await interaction.response.send_message("📩 Acesse o suporte pelo link: https://discord.gg/6H6EP96zRa", ephemeral=True)

TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)


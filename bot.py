import discord
from discord.ext import commands
import random
import os
from threading import Thread
from flask import Flask

# --- MINI SERVEUR WEB POUR METTRE LE BOT H24 ---
app = Flask('')

@app.route('/')
def home():
    return "Le bot de l'Archi-Duc est vivant !"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# -----------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

FILE_NAME = "missions.txt"

def charger_missions_fichier():
    structure = {"commune": [], "moyenne": [], "difficile": [], "royal": []}
    if not os.path.exists(FILE_NAME):
        return structure
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line:
                continue
            cat, texte, delai = line.split("|", 2)
            if cat in structure:
                structure[cat].append({"texte": texte, "delai": delai})
    return structure

def réécrire_toutes_missions(structure):
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        for cat, liste in structure.items():
            for m in liste:
                f.write(f"{cat}|{m['texte']}|{m['delai']}\n")

def sauvegarder_mission_fichier(categorie, texte, delai):
    with open(FILE_NAME, "a", encoding="utf-8") as f:
        f.write(f"{categorie}|{texte}|{delai}\n")

missions_dispo = charger_missions_fichier()
missions_actives = {}

@bot.event
async def on_ready():
    print(f"Le Bot MADAmission H24 Pro est en ligne ! : {bot.user}")

@bot.event
async def on_message(message):
    global missions_dispo
    if message.author.bot:
        return

    content = message.content.strip()
    content_lower = content.lower()

    # 1. COMMANDE COMMUNE : !aide ou !help (NOUVEAU !)
    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(
            title="⚜️ TABLEAU DES ORDRES - MADAMISSION ⚜️",
            description="Voici la liste des commandes disponibles pour interagir avec le Royaume.",
            color=discord.Color.gold()
        )
        
        # Section Citoyens
        embed.add_field(
            name="👥 COMMANDES CITOYENS",
            value=(
                "**`!mission <difficulté>`**\n"
                "Demander un ordre aléatoire (Choix : `commune`, `moyenne`, `difficile`, `royal`).\n"
                "*Exemple : `!mission commune`*\n\n"
                "**`!rendre`**\n"
                "Valider/rendre votre mission en cours pour pouvoir en prendre une autre."
            ),
            inline=False
        )
        
        # Section Admins
        if message.author.guild_permissions.administrator:
            embed.add_field(
                name="👑 COMMANDES ADMINISTRATEUR",
                value=(
                    "**`!listemissions`**\n"
                    "Afficher la liste complète de toutes les missions enregistrées.\n\n"
                    "**`!addmission <difficulté> <mission> pendant <délai>`**\n"
                    "Ajouter un nouvel ordre au Royaume.\n"
                    "*Exemple : `!addmission commune Miner 64 fer pendant 1 jour`*\n\n"
                    "**`!delmission <difficulté> <numéro>`**\n"
                    "Supprimer une mission spécifique grâce à son numéro.\n"
                    "*Exemple : `!delmission commune 2`*"
                ),
                inline=False
            )
            
        embed.set_footer(text="Que la gloire du Royaume vous accompagne.")
        await message.channel.send(embed=embed)
        return

    # 2. COMMANDE ADMIN : !listemissions
    if content_lower.startswith("!listemissions"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Seuls les administrateurs peuvent voir la liste complète.")
            return
        missions_dispo = charger_missions_fichier()
        reponse = "⚜️ **LISTE DES MISSIONS DU ROYAUME DE MADAGASCAR** ⚜️\n\n"
        emojis = {"commune": "🟢", "moyenne": "🔵", "difficile": "🟠", "royal": "👑"}
        titres = {"commune": "COMMUNES", "moyenne": "MOYENNES", "difficile": "DIFFICILES", "royal": "ROYALES"}
        total_missions = 0
        for cat in ["commune", "moyenne", "difficile", "royal"]:
            reponse += f"{emojis[cat]} __**Missions {titres[cat]} :**__\n"
            if not missions_dispo[cat]:
                reponse += "*Aucune mission enregistrée dans cette catégorie.*\n"
            else:
                for i, m in enumerate(missions_dispo[cat], start=1):
                    reponse += f"**{i}.** {m['texte']} *(Délai : {m['delai']})*\n"
                    total_missions += 1
            reponse += "\n"
        reponse += f"📊 *Total : {total_missions} mission(s) disponible(s).*js"
        if len(reponse) > 2000:
            await message.channel.send("⚠️ Liste trop longue, consultez le fichier texte.")
        else:
            await message.channel.send(reponse)
        return

    # 3. COMMANDE ADMIN : !addmission
    if content_lower.startswith("!addmission"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Seuls les administrateurs peuvent ajouter des missions.")
            return
        
        texte_total = content[11:].strip()
        mots = texte_total.split()
        
        if len(mots) < 4 or "pendant" not in texte_total.lower():
            await message.channel.send("❌ Mauvais format ! Exemple : `!addmission commune Miner fer pendant 1 jour`")
            return
            
        cat = mots[0].lower()
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else:
            await message.channel.send("❌ Catégorie invalide. Choix : `commune`, `moyenne`, `difficile`, `royal`.")
            return

        parties = texte_total.split(None, 1)[1].strip()
        index_pendant = parties.lower().rfind("pendant")
        
        texte_mission = parties[:index_pendant].strip()
        delai = parties[index_pendant + 7:].strip()
        
        if not texte_mission or not delai:
            await message.channel.send("❌ Erreur de format. Écris la mission, puis le mot `pendant`, puis le délai.")
            return

        sauvegarder_mission_fichier(cat, texte_mission, delai)
        missions_dispo = charger_missions_fichier()
        await message.channel.send(f"⚜️ **Mission ajoutée !**\nCatégorie : `{cat}`\nMission : *{texte_mission}*\nDélai : *{delai}*")
        return

    # 4. COMMANDE ADMIN : !delmission
    if content_lower.startswith("!delmission"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Seuls les administrateurs peuvent supprimer des missions.")
            return
        
        mots = content_lower.split()
        if len(mots) < 3:
            await message.channel.send("❌ Mauvais format ! Exemple : `!delmission commune 2`")
            return
            
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else:
            await message.channel.send("❌ Catégorie invalide.")
            return
            
        try:
            numero = int(mots[2]) - 1
        except ValueError:
            await message.channel.send("❌ Le numéro doit être un chiffre valide.")
            return
            
        missions_dispo = charger_missions_fichier()
        if numero < 0 or numero >= len(missions_dispo[cat]):
            await message.channel.send(f"❌ Numéro invalide. Pas de mission n°{numero+1} dans `{cat}`.")
            return
            
        mission_supprimee = missions_dispo[cat].pop(numero)
        réécrire_toutes_missions(missions_dispo)
        await message.channel.send(f"🗑️ **Mission retirée !**\n*\"{mission_supprimee['texte']}\"* a été supprimée de la catégorie `{cat}`.")
        return

    # 5. COMMANDE CITOYENS : !mission
    if content_lower.startswith("!mission"):
        joueur = message.author
        mots = content_lower.split()
        if len(mots) < 2:
            await message.channel.send(f"❌ {joueur.mention}, précise la difficulté.")
            return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else:
            await message.channel.send("❌ Difficulté inconnue.")
            return
        if joueur.id in missions_actives:
            await message.channel.send(f"❌ {joueur.mention}, tu as déjà une mission active !")
            return
        if not missions_dispo[cat]:
            await message.channel.send(f"⚪ Aucune mission de type **{cat}** disponible.")
            return
        mission_choisie = random.choice(missions_dispo[cat])
        missions_actives[joueur.id] = mission_choisie["texte"]
        reponse = f"**Archi-Duc** {joueur.mention}, **Voici votre mission {cat} :**\n• *{mission_choisie['texte']}*\n• *Délai : {mission_choisie['delai']}*"
        await message.channel.send(reponse)
        return

    # 6. COMMANDE CITOYENS : !rendre
    if content_lower == "!rendre":
        joueur = message.author
        if joueur.id in missions_actives:
            del missions_actives[joueur.id]
            await message.channel.send(f"✅ **Archi-Duc** {joueur.mention}, mission rendue !")
        else:
            await message.channel.send(f"❌ Tu n'as pas de mission en cours.")

# Configuration et lancement
keep_alive()
token = os.environ.get("DISCORD_TOKEN", "TON_TOKEN_ICI")
bot.run(token)

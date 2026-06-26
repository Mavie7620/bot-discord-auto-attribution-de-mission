import discord
from discord.ext import commands, tasks
import random
import os
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta

app = Flask('')

@app.route('/')
def home(): return "Le bot de l'Archi-Duc est vivant !"

def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_web)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

FILE_NAME = "missions.txt"

def charger_missions_fichier():
    structure = {"commune": [], "moyenne": [], "difficile": [], "royal": []}
    if not os.path.exists(FILE_NAME): return structure
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line: continue
            cat, texte, delai = line.split("|", 2)
            if cat in structure: structure[cat].append({"texte": texte, "delai": delai})
    return structure

def réécrire_toutes_missions(structure):
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        for cat, liste in structure.items():
            for m in liste: f.write(f"{cat}|{m['texte']}|{m['delai']}\n")

def sauvegarder_mission_fichier(categorie, texte, delai):
    with open(FILE_NAME, "a", encoding="utf-8") as f: f.write(f"{categorie}|{texte}|{delai}\n")

def extraire_duree(delai_texte):
    mots = delai_texte.lower().split()
    valeur = 1
    for i, mot in enumerate(mots):
        try: valeur = float(mots[i-1].replace(",", "."))
        except (ValueError, IndexError): continue
        if "min" in mot or "mn" in mot: return timedelta(minutes=valeur)
        if "heure" in mot or "hour" in mot or "h" == mot: return timedelta(hours=valeur)
        if "jour" in mot or "day" in mot or "j" == mot: return timedelta(days=valeur)
        if "semaine" in mot or "week" in mot: return timedelta(weeks=valeur)
        if "mois" in mot or "moi" in mot or "month" in mot: return timedelta(days=valeur * 30)
    return timedelta(days=3)

missions_dispo = charger_missions_fichier()
missions_actives = {}

@tasks.loop(seconds=1)
async def verifier_temps_missions():
    maintenant = datetime.now()
    joueurs_en_retard = []
    for j_id, m_info in list(missions_actives.items()):
        channel = bot.get_channel(m_info["channel_id"])
        if not channel: continue
        guild = channel.guild
        membre = guild.get_member(j_id)
        mention_membre = membre.mention if membre else f"<@{j_id}>"
        duree_totale = m_info["duree_totale"]
        date_debut = m_info["date_debut"]
        date_fin = m_info["date_fin"]
        temps_restant = date_fin - maintenant
        temps_ecoule = maintenant - date_debut

        if maintenant > date_fin:
            joueurs_en_retard.append(j_id)
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            role_instructeur = discord.utils.get(guild.roles, name="Instructeur")
            if not role_instructeur:
                try: role_instructeur = await guild.create_role(name="Instructeur", mentionable=True, color=discord.Color.blue())
                except discord.Forbidden: role_instructeur = None
            mention_instructeur = role_instructeur.mention if role_instructeur else "@Instructeur"
            
            # Message d'échec de moins de 15 lignes avec l'article V mis en valeur
            await channel.send(
                f"🚨 **MISSION ÉCHOUÉE** 🚨\n"
                f"Le temps imparti est écoulé ! La mission de {mention_membre} a échoué.\n"
                f"📢 **Avis aux supérieurs :** {mention_instructeur}, un citoyen n'a pas honoré son décret à temps.\n\n"
                f"⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖚 𝕽𝖔𝖞𝖆𝖚𝖒𝖊** ⚜️\n"
                f"**D'après l'article Ⅴ — Rappel :**\n"
                f"- **Refuser ou abandonner une mission attribuée sans raison valable peut être sanctionné.**\n"
                f"- *Le Royaume récompense l'investissement et la persévérance.*\n"
                f"- *Les missions constituent l'un des principaux moyens de progresser au sein du Royaume.*"
            )
        elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
            m_info["alerte_un_quart"] = True
            m_info["alerte_moitie"] = True
            jours = temps_restant.days
            heures, reste = divmod(temps_restant.seconds, 3600)
            minutes, secondes = divmod(reste, 60)
            await channel.send(f"⏳ **CRITIQUE** {mention_membre} : -25% du temps ! Reste : `{jours}j {heures}h {minutes}mn {secondes}s` !")
        elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
            m_info["alerte_moitie"] = True
            await channel.send(f"🌗 **MI-PARCOURS** {mention_membre} : la moitié du temps s'est écoulée !")

    for j_id in joueurs_en_retard:
        if j_id in missions_actives: del missions_actives[j_id]

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    print("Bot MADAmission avec article V mis en gras en ligne !")

@bot.event
async def on_message(message):
    global missions_dispo
    if message.author.bot: return
    content = message.content.strip()
    content_lower = content.lower()

    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES ⚜️", color=discord.Color.gold())
        embed.add_field(name="👥 SOLDAT", value="`!mission <difficulté>`\n`!fin`", inline=False)
        if message.author.guild_permissions.administrator:
            embed.add_field(name="👑 INSTRUCTEUR", value="`!missionfinit @joueur`\n`!listemissions`\n`!addmission <diff> <texte> pendant <délai>`\n`!delmission <diff> <num>`", inline=False)
        await message.channel.send(embed=embed)
        return

    if content_lower == "!fin":
        joueur = message.author
        if joueur.id not in missions_actives:
            await message.channel.send(f"❌ {joueur.mention}, aucune mission active.")
            return
        role_instructeur = discord.utils.get(message.guild.roles, name="Instructeur")
        m_info = missions_actives[joueur.id]
        await message.channel.send(f"📢 {role_instructeur.mention if role_instructeur else '@Instructeur'} ! {joueur.mention} a fini : *\"{m_info['texte']}\"* !")
        return

    if content_lower.startswith("!missionfinit"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions: return
        cible = message.mentions[0]
        if cible.id in missions_actives:
            del missions_actives[cible.id]
            await message.channel.send(f"✅ Mission de {cible.mention} validée et retirée !")
        else:
            await message.channel.send(f"❌ Aucune mission active pour lui.")
        return

    if content_lower.startswith("!listemissions"):
        if not message.author.guild_permissions.administrator: return
        missions_dispo = charger_missions_fichier()
        reponse = "⚜️ **ARCHIVES** ⚜️\n"
        for cat in ["commune", "moyenne", "difficile", "royal"]:
            reponse += f"__**{cat.upper()} :**__\n"
            if not missions_dispo[cat]: reponse += "*Vide*\n"
            else:
                for i, m in enumerate(missions_dispo[cat], start=1): reponse += f"**{i}.** {m['texte']} *({m['delai']})*\n"
        await message.channel.send(reponse)
        return

    if content_lower.startswith("!addmission"):
        if not message.author.guild_permissions.administrator: return
        texte_total = content[11:].strip()
        mots = texte_total.split()
        if len(mots) < 4 or "pendant" not in texte_total.lower(): return
        cat = mots[0].lower()
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else: return
        parties = texte_total.split(None, 1)[1].strip()
        index_pendant = parties.lower().rfind("pendant")
        texte_mission = parties[:index_pendant].strip()
        delai = parties[index_pendant + 7:].strip()
        sauvegarder_mission_fichier(cat, texte_mission, delai)
        missions_dispo = charger_missions_fichier()
        await message.channel.send(f"⚜️ **Ajoutée !** (`{cat}` : *{texte_mission}*)")
        return

    if content_lower.startswith("!delmission"):
        if not message.author.guild_permissions.administrator: return
        mots = content_lower.split()
        if len(mots) < 3: return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        try: numero = int(mots[2]) - 1
        except ValueError: return
        missions_dispo = charger_missions_fichier()
        if numero >= 0 and numero < len(missions_dispo[cat]):
            missions_dispo[cat].pop(numero)
            réécrire_toutes_missions(missions_dispo)
            await message.channel.send("🗑️ Mission retirée.")
        return

    if content_lower.startswith("!mission"):
        joueur = message.author
        mots = content_lower.split()
        if len(mots) < 2: return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else: return

        if joueur.id in missions_actives:
            await message.channel.send(f"❌ Tu as déjà une mission en cours !")
            return

        missions_dispo = charger_missions_fichier()
        if not missions_dispo[cat]:
            await message.channel.send(f"⚪ Aucune mission **{cat}** disponible.")
            return

        index_choisi = random.randint(0, len(missions_dispo[cat]) - 1)
        mission_choisie = missions_dispo[cat].pop(index_choisi)
        réécrire_toutes_missions(missions_dispo)

        duree_calculee = extraire_duree(mission_choisie["delai"])
        maintenant_debut = datetime.now()
        date_limite = maintenant_debut + duree_calculee

        missions_actives[joueur.id] = {
            "texte": mission_choisie["texte"],
            "delai_texte": mission_choisie["delai"],
            "date_debut": maintenant_debut,
            "date_fin": date_limite,
            "duree_totale": duree_calculee,
            "cat": cat,
            "channel_id": message.channel.id,
            "alerte_moitie": False,
            "alerte_un_quart": False
        }
        await message.channel.send(f"Mission : *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
        return

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN", "TON_TOKEN_ICI"))

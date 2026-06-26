import discord
from discord.ext import commands
import random
import os
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta

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

def extraire_jours(delai_texte):
    mots = delai_texte.lower().split()
    for i, mot in enumerate(mots):
        if "jour" in mot or "day" in mot:
            try: return int(mots[i-1])
            except (ValueError, IndexError): return 1
        if "heure" in mot or "hour" in mot:
            try: return int(mots[i-1]) / 24.0
            except (ValueError, IndexError): return 0.1
    return 3

missions_dispo = charger_missions_fichier()
missions_actives = {}  # {joueur_id: {"texte": ..., "date_fin": ..., "cat": ..., "alerte_2h": False}}

@bot.event
async def on_ready():
    print(f"Le Bot MADAmission Pro avec alertes de temps est en ligne !")

@bot.event
async def on_message(message):
    global missions_dispo
    if message.author.bot:
        return

    content = message.content.strip()
    content_lower = content.lower()

    # --- SÉCURITÉ & VÉRIFICATION DU TEMPS (ALERTES ET RETARDS) ---
    maintenant = datetime.now()
    joueurs_en_retard = []
    
    for j_id, m_info in list(missions_actives.items()):
        membre = message.guild.get_member(j_id)
        mention_membre = membre.mention if membre else f"<@{j_id}>"
        
        # 1. Alerte retard (le temps est dépassé)
        if maintenant > m_info["date_fin"]:
            joueurs_en_retard.append(j_id)
            await message.channel.send(f"🚨 **ALERTE RETARD** 🚨\nLe temps est écoulé ! La mission de {mention_membre} n'a pas été finie à temps ! Le Roi est déçu. 👑")
            
        # 2. Alerte temps restant (moins de 2 heures restantes et pas encore alerté)
        elif m_info["date_fin"] - maintenant <= timedelta(hours=2) and not m_info["alerte_2h"]:
            m_info["alerte_2h"] = True # On marque l'alerte comme envoyée
            await message.channel.send(f"⏳ **SABLIER PRESQUE VIDE** ⏳\nSoldat {mention_membre}, il vous reste **moins de 2 heures** pour accomplir votre mission : *\"{m_info['texte']}\"* ! Dépêchez-vous !")

    for j_id in joueurs_en_retard:
        if j_id in missions_actives:
            del missions_actives[j_id]

    # 1. COMMANDE COMMUNE : !aide
    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(
            title="⚜️ TABLEAU DES ORDRES - MADAMISSION ⚜️",
            description="Voici la liste des commandes du Royaume.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="👥 COMMANDES SOLDAT",
            value=(
                "**`!mission <difficulté>`**\n"
                "Demander un ordre (Choix : `commune`, `moyenne`, `difficile`, `royal`).\n"
                "*RP : Pour signaler la fin, faites simplement : `@instructeur j'ai finit ma mission`*"
            ),
            inline=False
        )
        if message.author.guild_permissions.administrator:
            embed.add_field(
                name="👑 COMMANDES INSTRUCTEUR (ADMIN)",
                value=(
                    "**`!missionfinit @joueur`**\n"
                    "Valider officiellement la mission d'un soldat.\n\n"
                    "**`!listemissions`** | **`!addmission`** | **`!delmission`**"
                ),
                inline=False
            )
        await message.channel.send(embed=embed)
        return

    # 2. COMMANDE INSTRUCTEUR : !missionfinit @joueur
    if content_lower.startswith("!missionfinit"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Seuls les instructeurs (administrateurs) peuvent valider les missions.")
            return
        if not message.mentions:
            await message.channel.send("❌ Tu dois mentionner le soldat (ex: `!missionfinit @Mavie7620`).")
            return
        cible = message.mentions[0]
        if cible.id in missions_actives:
            del missions_actives[cible.id]
            await message.channel.send(f"✅ **L'instructeur {message.author.mention} a vérifié et validé !** La mission de {cible.mention} est officiellement accomplie. Gloire au Royaume ! ⚜️")
        else:
            await message.channel.send(f"❌ {cible.mention} n'a aucune mission active en ce moment.")
        return

    # 3. COMMANDE ADMIN : !listemissions
    if content_lower.startswith("!listemissions"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ Seuls les administrateurs peuvent voir la liste.")
            return
        missions_dispo = charger_missions_fichier()
        reponse = "⚜️ **LISTE DES MISSIONS DU ROYAUME** ⚜️\n\n"
        emojis = {"commune": "🟢", "moyenne": "🔵", "difficile": "🟠", "royal": "👑"}
        for cat in ["commune", "moyenne", "difficile", "royal"]:
            reponse += f"{emojis[cat]} __**Missions {cat.upper()} :**__\n"
            if not missions_dispo[cat]:
                reponse += "*Aucune mission.*\n"
            else:
                for i, m in enumerate(missions_dispo[cat], start=1):
                    reponse += f"**{i}.** {m['texte']} *(Délai : {m['delai']})*\n"
            reponse += "\n"
        await message.channel.send(reponse)
        return

    # 4. COMMANDE ADMIN : !addmission
    if content_lower.startswith("!addmission"):
        if not message.author.guild_permissions.administrator: return
        texte_total = content[11:].strip()
        mots = texte_total.split()
        if len(mots) < 4 or "pendant" not in texte_total.lower():
            await message.channel.send("❌ Exemple : `!addmission commune Miner fer pendant 1 jour`")
            return
        cat = mots[0].lower()
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else:
            await message.channel.send("❌ Catégorie invalide.")
            return
        parties = texte_total.split(None, 1)[1].strip()
        index_pendant = parties.lower().rfind("pendant")
        texte_mission = parties[:index_pendant].strip()
        delai = parties[index_pendant + 7:].strip()
        sauvegarder_mission_fichier(cat, texte_mission, delai)
        missions_dispo = charger_missions_fichier()
        await message.channel.send(f"⚜️ **Mission ajoutée !** (`{cat}` : *{texte_mission}*)")
        return

    # 5. COMMANDE ADMIN : !delmission
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

    # 6. COMMANDE SOLDAT : !mission <difficulté>
    if content_lower.startswith("!mission"):
        joueur = message.author
        mots = content_lower.split()
        if len(mots) < 2:
            await message.channel.send(f"❌ Précise la difficulté (commune, moyenne, difficile, royal).")
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
            await message.channel.send(f"❌ Soldat {joueur.mention}, tu as déjà une mission en cours !")
            return

        if not missions_dispo[cat]:
            await message.channel.send(f"⚪ Aucune mission de type **{cat}** disponible.")
            return

        mission_choisie = random.choice(missions_dispo[cat])
        
        jours_delai = extraire_jours(mission_choisie["delai"])
        date_limite = datetime.now() + timedelta(days=jours_delai)

        missions_actives[joueur.id] = {
            "texte": mission_choisie["texte"],
            "date_fin": date_limite,
            "cat": cat,
            "alerte_2h": False  # Initialisé à False pour pouvoir déclencher l'alerte plus tard
        }

        await message.channel.send(f"Votre mission est la suivante : *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
        return

# Lancement
keep_alive()
token = os.environ.get("DISCORD_TOKEN", "TON_TOKEN_ICI")
bot.run(token)

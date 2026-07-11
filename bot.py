import discord
from discord.ext import commands, tasks
import random
import os
import json
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta

app = Flask('')

@app.route('/')
def home(): return "Le bot de Madagascar est vivant !"

def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_web)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

FILE_NAME = "missions.txt"
PROFILES_FILE = "profils.txt"

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

def charger_profils():
    if not os.path.exists(PROFILES_FILE): return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def sauvegarder_profils(profils):
    with open(PROFILES_FILE, "w", encoding="utf-8") as f: json.dump(profils, f, indent=4, ensure_ascii=False)

def initialiser_profil(p_id, profils):
    s_id = str(p_id)
    if s_id not in profils:
        profils[s_id] = {
            "total_reussies": 0,
            "total_echouees": 0,
            "historique": []
        }

def ajouter_historique(p_id, profils, texte, statut):
    s_id = str(p_id)
    initialiser_profil(p_id, profils)
    profils[s_id]["historique"].insert(0, {
        "texte": texte,
        "statut": statut,
        "date": datetime.now().strftime("%d/%m/%Y à %H:%M")
    })

def extraire_duree(delai_texte):
    mots = delai_texte.lower().replace("pour dans", "").replace("pour", "").strip().split()
    valeur = 1
    for i, mot in enumerate(mots):
        try: valeur = float(mots[i-1].replace(",", "."))
        except (ValueError, IndexError): continue
        if "min" in mot or "mn" in mot: return timedelta(minutes=valeur)
        if "heure" in mot or "hour" in mot or "h" in mot: return timedelta(hours=valeur)
        if "jour" in mot or "day" in mot or "j" in mot: return timedelta(days=valeur)
        if "semaine" in mot or "week" in mot: return timedelta(weeks=valeur)
        if "mois" in mot or "moi" in mot or "month" in mot: return timedelta(days=valeur * 30)
    return timedelta(days=3)

missions_dispo = charger_missions_fichier()
missions_actives = {}

TEXTE_ECHEC = (
    "⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖊 𝕸𝖆𝖉𝖆𝖈𝖆𝖘𝖈𝖆𝖗** ⚜️\n"
    "**D'après l'article Ⅴ — Rappel :**\n"
    "- **Refuser ou abandonner une mission attribuée sans raison valable peut être sanctionné.**\n"
    "- *L'État récompense l'investissement et la persévérance.*\n"
    "- *Les missions constituent l'un des principaux moyens de progresser au sein de Madagascar.*"
)

@tasks.loop(seconds=1)
async def verifier_temps_missions():
    maintenant = datetime.now()
    missions_a_retirer = []
    
    for joueur_id, m_info in list(missions_actives.items()):
        if m_info.get("en_attente", False): continue
        
        channel = bot.get_channel(m_info["channel_id"])
        if not channel: continue
        
        duree_totale = m_info["duree_totale"]
        date_debut = m_info["date_debut"]
        date_fin = m_info["date_fin"]
        temps_restant = date_fin - maintenant
        temps_ecoule = maintenant - date_debut

        if maintenant > date_fin:
            missions_a_retirer.append(joueur_id)
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            
            profils = charger_profils()
            initialiser_profil(joueur_id, profils)
            profils[str(joueur_id)]["total_echouees"] += 1
            ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            role_instructeur = discord.utils.get(channel.guild.roles, name="Instructeur")
            await channel.send(
                f"🚨 **MISSION ÉCHOUÉE** 🚨\nLe temps imparti est écoulé ! La mission de <@{joueur_id}> a échoué.\n"
                f"📢 {role_instructeur.mention if role_instructeur else '@Instructeur'}, un citoyen a failli à son devoir.\n\n{TEXTE_ECHEC}"
            )
        elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
            m_info["alerte_un_quart"] = True
            m_info["alerte_moitie"] = True
            jours = temps_restant.days
            heures, reste = divmod(temps_restant.seconds, 3600)
            minutes, secondes = divmod(reste, 60)
            await channel.send(f"⏳ **CRITIQUE** <@{joueur_id}> : -25% du temps restant ! Reste : `{jours}j {heures}h {minutes}mn {secondes}s` !")
        elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
            m_info["alerte_moitie"] = True
            await channel.send(f"🌗 **MI-PARCOURS** <@{joueur_id}> : la moitié du temps s'est écoulée !")

    for joueur_id in missions_a_retirer:
        if joueur_id in missions_actives: del missions_actives[joueur_id]

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    print("Bot MADAmission Épuré opérationnel !")

@bot.event
async def on_message(message):
    global missions_dispo
    if message.author.bot: return
    content = message.content.strip()
    content_lower = content.lower()

    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES DE MADAGASCAR ⚜️", color=discord.Color.gold())
        
        citoyen_desc = (
            "⚔️ **SYSTÈME DE QUÊTES**\n"
            "`!mission <difficulté>`\n↳ Pioche une mission en solo (`commune`, `moyenne`, `difficile`, `royal`).\n\n"
            "`!missionacomplis`\n↳ Met le chrono en pause et alerte les Instructeurs pour vérification.\n\n"
            "`!missions_en_cours`\n↳ Affiche le statut de ta tâche active.\n\n"
            "📊 **ARCHIVES PERSONNELLES**\n"
            "`!historique [@joueur]`\n↳ Consulte le journal complet, le nombre de réussites et d'échecs."
        )
        embed.add_field(name="👥 ESPACE DES CITOYENS", value=citoyen_desc, inline=False)
        
        if message.author.guild_permissions.administrator:
            admin_desc = (
                "🚨 **HAUT COMMANDEMENT (ADMINISTRATEUR)**\n"
                "`!missionfinit @joueur`\n↳ Valide définitivement l'objectif réussi du joueur.\n\n"
                "`!missionechec @joueur`\n↳ Invalide la quête : elle retourne dans le catalogue et inflige un échec consigné dans l'historique.\n\n"
                "📂 **BASE DE DONNÉES DES MISSIONS**\n"
                "`!listemissions`\n↳ Liste l'intégralité des quêtes enregistrées.\n\n"
                "`!addmission <difficulté> <texte> pendant <temps>`\n↳ Enregistre un nouveau décret (Ex: `commune Miner du fer pendant 1h`).\n\n"
                "`!delmission <difficulté> <numéro>`\n↳ Supprime définitivement une quête via son numéro de liste."
            )
            embed.add_field(name="👑 ADMINISTRATION", value=admin_desc, inline=False)
            
        await message.channel.send(embed=embed)
        return

    if content_lower == "!missions_en_cours":
        if message.author.id not in missions_actives:
            await message.channel.send("⚪ Tu n'as aucune mission active actuellement.")
            return
            
        m = missions_actives[message.author.id]
        t_rest = m["date_fin"] - datetime.now()
        jours = max(0, t_rest.days)
        heures, reste = divmod(max(0, t_rest.seconds), 3600)
        minutes, _ = divmod(reste, 60)
        
        if m.get("en_attente", False):
            await message.channel.send(f"👤 <@{message.author.id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* 🛑 **GELÉ (En attente d'évaluation)**")
        else:
            await message.channel.send(f"👤 <@{message.author.id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* (Reste : `{jours}j {heures}h {minutes}m`)")
        return

    if content_lower == "!missionacomplis":
        joueur = message.author
        role_instructeur = discord.utils.get(message.guild.roles, name="Instructeur")
        mention_ins = role_instructeur.mention if role_instructeur else '@Instructeur'
        
        if joueur.id in missions_actives:
            m_info = missions_actives[joueur.id]
            if not m_info.get("en_attente", False):
                m_info["en_attente"] = True
                m_info["moment_gel"] = datetime.now()
            await message.channel.send(f"📢 {mention_ins} ! {joueur.mention} déclare avoir fini sa mission : *\"{m_info['texte']}\"* !\n⏱️ **Le chrono est mis en pause le temps des vérifications.**")
            return
            
        await message.channel.send("❌ Tu n'as aucune mission active en cours.")
        return

    if content_lower.startswith("!missionfinit"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions: return
        cible = message.mentions[0]
        
        if cible.id in missions_actives:
            m_info = missions_actives[cible.id]
            profils = charger_profils()
            initialiser_profil(cible.id, profils)
            
            profils[str(cible.id)]["total_reussies"] += 1
            ajouter_historique(cible.id, profils, m_info["texte"], "Succès")
            sauvegarder_profils(profils)
            
            del missions_actives[cible.id]
            await message.channel.send(f"✅ Mission validée avec succès par le Haut Commandement pour {cible.mention} !")
            return
        await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
        return

    if content_lower.startswith("!missionechec"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions: return
        cible = message.mentions[0]
        
        if cible.id in missions_actives:
            m_info = missions_actives[cible.id]
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            
            profils = charger_profils()
            initialiser_profil(cible.id, profils)
            
            profils[str(cible.id)]["total_echouees"] += 1
            ajouter_historique(cible.id, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            del missions_actives[cible.id]
                
            await message.channel.send(
                f"↩️ **Mission invalidée par l'Instructeur pour {cible.mention}.** La quête retourne dans le catalogue.\n"
                f"📉 **Conséquence :** Un échec a été enregistré dans l'historique du joueur.\n\n{TEXTE_ECHEC}"
            )
            return
            
        await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
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
            await message.channel.send("❌ Tu as déjà une mission en cours !")
            return

        missions_dispo = charger_missions_fichier()
        if not missions_dispo[cat]:
            await message.channel.send("❌ Plus de mission disponible dans cette catégorie.")
            return
        mission_choisie = missions_dispo[cat].pop(random.randint(0, len(missions_dispo[cat]) - 1))
        réécrire_toutes_missions(missions_dispo)

        duree = extraire_duree(mission_choisie["delai"])
        missions_actives[joueur.id] = {
            "texte": mission_choisie["texte"], "delai_texte": mission_choisie["delai"],
            "date_debut": datetime.now(), "date_fin": datetime.now() + duree, "duree_totale": duree,
            "cat": cat, "channel_id": message.channel.id, "alerte_moitie": False, "alerte_un_quart": False, "en_attente": False
        }
        await message.channel.send(f"📜 **Mission attribuée :** *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
        return

    if content_lower.startswith("!listemissions") and message.author.guild_permissions.administrator:
        missions_dispo = charger_missions_fichier()
        reponse = "⚜️ **ARCHIVES DES MISSIONS DISPONIBLES** ⚜️\n"
        for cat in ["commune", "moyenne", "difficile", "royal"]:
            reponse += f"\n__**{cat.upper()} :**__\n"
            if not missions_dispo[cat]: reponse += "*Aucune mission disponible*\n"
            else:
                for i, m in enumerate(missions_dispo[cat], start=1): reponse += f"**{i}.** {m['texte']} *(Délai d'origine : {m['delai']})*\n"
        await message.channel.send(reponse[:2000])
        return

    if content_lower.startswith("!addmission") and message.author.guild_permissions.administrator:
        texte_total = content[11:].strip()
        mots = texte_total.split()
        if len(mots) < 4 or "pendant" not in texte_total.lower():
            await message.channel.send("❌ Format incorrect. Exemple : `!addmission commune Miner 50 diamants pendant 2h`")
            return
        cat = mots[0].lower()
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else:
            await message.channel.send("❌ Catégorie inconnue (`commune`, `moyenne`, `difficile`, `royal`).")
            return
        parties = texte_total.split(None, 1)[1].strip()
        index_pendant = parties.lower().rfind("pendant")
        texte_mission = parties[:index_pendant].strip()
        delai = parties[index_pendant + 7:].strip()
        sauvegarder_mission_fichier(cat, texte_mission, delai)
        missions_dispo = charger_missions_fichier()
        await message.channel.send(f"⚜️ **Mission ajoutée au catalogue !** (`{cat}` : *{texte_mission}*)")
        return

    if content_lower.startswith("!delmission") and message.author.guild_permissions.administrator:
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
        if cat in missions_dispo and 0 <= numero < len(missions_dispo[cat]):
            retiree = missions_dispo[cat].pop(numero)
            réécrire_toutes_missions(missions_dispo)
            await message.channel.send(f"🗑️ Mission *\"{retiree['texte']}\"* supprimée avec succès.")
        else:
            await message.channel.send("❌ Numéro invalide ou mission introuvable.")
        return

    # --- HISTORIQUE ET COMPTEURS DES DECRETS ---
    if content_lower.startswith("!historique"):
        cible = message.mentions[0] if message.mentions else message.author
        profils = charger_profils()
        initialiser_profil(cible.id, profils)
        
        userData = profils[str(cible.id)]
        hist = userData["historique"]
        
        embed = discord.Embed(
            title=f"📜 ARCHIVES ET PARCHEMIN — {cible.display_name}", 
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=cible.display_avatar.url)
        
        # Affichage du système de compteurs uniques (nombre de missions totales)
        cpt_txt = f"🟢 **Missions Réussies :** `{userData['total_reussies']}`\n🔴 **Missions Échouées :** `{userData['total_echouees']}`"
        embed.add_field(name="📊 Bilan des Objectifs", value=cpt_txt, inline=False)
        
        # Liste de l'intégralité de l'historique
        if not hist:
            embed.add_field(name="📜 Historique des Décrets", value="*Aucune mission enregistrée dans le grand registre.*", inline=False)
        else:
            hist_lignes = []
            for item in hist:
                emoji = "✅" if item["statut"] == "Succès" else "❌"
                hist_lignes.append(f"{emoji} **[{item['date']}]** — {item['texte']}")
            
            # Gestion de la taille du message si l'historique devient extrêmement long
            corps_historique = "\n".join(hist_lignes)
            if len(corps_historique) > 1024:
                corps_historique = corps_historique[:1000] + "\n*... (suite tronquée)*"
                
            embed.add_field(name="📜 Historique des Décrets", value=corps_historique, inline=False)
            
        await message.channel.send(embed=embed)
        return

keep_alive()
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Erreur : Aucun token Discord trouvé.")

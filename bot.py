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
def home(): return "Le bot de l'Archi-Duc est vivant !"

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
            "reussies": {"commune": 0, "moyenne": 0, "difficile": 0, "royal": 0},
            "echouees": {"commune": 0, "moyenne": 0, "difficile": 0, "royal": 0},
            "historique": []
        }

def ajouter_historique(p_id, profils, texte, statut):
    s_id = str(p_id)
    initialiser_profil(p_id, profils)
    hist = profils[s_id]["historique"]
    hist.insert(0, {"texte": texte, "statut": statut, "date": datetime.now().strftime("%d/%m/%Y")})
    profils[s_id]["historique"] = hist[:5]

def calculer_rang(stats):
    r = stats["reussies"]
    if r["commune"] >= 20 and r["moyenne"] >= 10 and r["difficile"] >= 5 and r["royal"] >= 1:
        return "👑 Légende du Royaume"
    if r["commune"] >= 10 and r["moyenne"] >= 5 and r["difficile"] >= 1:
        return "⚔️ Vétéran"
    if r["commune"] >= 5:
        return "🛡️ Soldat"
    return "🔰 Recrue"

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

TEXTE_ECHEC = (
    "⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖚 𝕽𝖔𝖞𝖆𝖚𝖒𝖊** ⚜️\n"
    "**D'après l'article Ⅴ — Rappel :**\n"
    "- **Refuser ou abandonner une mission attribuée sans raison valable peut être sanctionné.**\n"
    "- *Le Royaume récompense l'investissement et la persévérance.*\n"
    "- *Les missions constituent l'un des principaux moyens de progresser au sein du Royaume.*"
)

@tasks.loop(seconds=1)
async def verifier_temps_missions():
    maintenant = datetime.now()
    missions_a_retirer = []

    for leader_id, m_info in list(missions_actives.items()):
        # Pour éviter les doublons dans les groupes, on ne traite la mission qu'une seule fois via son leader logique
        if m_info.get("traité_ce_cycle", False): continue
        
        channel = bot.get_channel(m_info["channel_id"])
        if not channel: continue
        guild = channel.guild
        
        escouade = m_info["membres"]
        mentions_membres = ", ".join([f"<@{uid}>" for uid in escouade])
        
        duree_totale = m_info["duree_totale"]
        date_debut = m_info["date_debut"]
        date_fin = m_info["date_fin"]
        temps_restant = date_fin - maintenant
        temps_ecoule = maintenant - date_debut

        # Marquer temporairement tous les membres de cette mission pour ne pas dupliquer les alertes
        for uid in escouade:
            if uid in missions_actives:
                missions_actives[uid]["traité_ce_cycle"] = True

        if maintenant > date_fin:
            missions_a_retirer.append(leader_id)
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            
            profils = charger_profils()
            for uid in escouade:
                initialiser_profil(uid, profils)
                profils[str(uid)]["echouees"][m_info["cat"]] += 1
                ajouter_historique(uid, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            role_instructeur = discord.utils.get(guild.roles, name="Instructeur")
            if not role_instructeur:
                try: role_instructeur = await guild.create_role(name="Instructeur", mentionable=True, color=discord.Color.blue())
                except discord.Forbidden: role_instructeur = None
            mention_instructeur = role_instructeur.mention if role_instructeur else "@Instructeur"
            
            await channel.send(
                f"🚨 **MISSION ÉCHOUÉE** 🚨\n"
                f"Le temps imparti est écoulé ! La mission de l'escouade ({mentions_membres}) a échoué.\n"
                f"📢 **Avis aux supérieurs :** {mention_instructeur}, des citoyens n'ont pas honoré leur décret à temps.\n\n"
                f"{TEXTE_ECHEC}"
            )
        elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
            m_info["alerte_un_quart"] = True
            m_info["alerte_moitie"] = True
            jours = temps_restant.days
            heures, reste = divmod(temps_restant.seconds, 3600)
            minutes, secondes = divmod(reste, 60)
            await channel.send(f"⏳ **CRITIQUE** {mentions_membres} : -25% du temps ! Reste : `{jours}j {heures}h {minutes}mn {secondes}s` !")
        elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
            m_info["alerte_moitie"] = True
            await channel.send(f"🌗 **MI-PARCOURS** {mentions_membres} : la moitié du temps s'est écoulée !")

    # Nettoyage et reset des flags de traitement
    for uid, m_info in list(missions_actives.items()):
        if "traité_ce_cycle" in m_info:
            del m_info["traité_ce_cycle"]

    for leader_id in missions_a_retirer:
        if leader_id in missions_actives:
            escouade = missions_actives[leader_id]["membres"]
            for uid in escouade:
                if uid in missions_actives: del missions_actives[uid]

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    print("Bot MADAmission Pro configuré avec missions de groupe !")

@bot.event
async def on_message(message):
    global missions_dispo
    if message.author.bot: return
    content = message.content.strip()
    content_lower = content.lower()

    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES DU ROYAUME ⚜️", color=discord.Color.gold())
        
        citoyen_desc = (
            "`!mission <difficulté>`\n↳ Pioche une mission solo aléatoire (`commune`, `moyenne`, `difficile`, `royal`).\n\n"
            "`!mission_groupe <difficulté> @joueur1 @joueur2...`\n↳ Lance une mission collective pour vous et les joueurs mentionnés. Tout le monde doit être libre.\n\n"
            "`!fin`\n↳ Signale aux Instructeurs que vous (ou votre escouade) estimez avoir accompli la mission active.\n\n"
            "`!missions_en_cours`\n↳ Affiche la liste globale de toutes les missions solo et collectives en cours dans le Royaume.\n\n"
            "`!profil [@joueur]`\n↳ Consulte votre profil (grade, statistiques de quêtes) ou celui d'un autre citoyen.\n\n"
            "`!historique`\n↳ Affiche vos 5 dernières actions (Missions réussies ou échouées) avec la date.\n\n"
            "`!stats_royaume`\n↳ Affiche les statistiques globales du Royaume (Efficacité générale, total de missions)."
        )
        embed.add_field(name="👥 CITOYENS & ESCOUADES", value=citoyen_desc, inline=False)
        
        if message.author.guild_permissions.administrator:
            admin_desc = (
                "`!missionfinit @joueur`\n↳ Valide la mission en cours du joueur (si c'est un groupe, valide toute l'escouade d'un coup).\n\n"
                "`!missionechec @joueur`\n↳ Annule et marque de force la mission du joueur (ou de son escouade entière) comme un échec.\n\n"
                "`!listemissions`\n↳ Affiche le registre complet de toutes les missions stockées.\n\n"
                "`!addmission <difficulté> <texte> pendant <délai>`\n↳ Ajoute un décret (Ex: `!addmission commune Miner du fer pendant 2 heures`).\n\n"
                "`!delmission <difficulté> <numéro>`\n↳ Supprime une mission spécifique du registre via son numéro."
            )
            embed.add_field(name="👑 INSTRUCTEURS (ADMIN)", value=admin_desc, inline=False)
            
        await message.channel.send(embed=embed)
        return

    if content_lower == "!missions_en_cours":
        if not missions_actives:
            await message.channel.send("⚪ Aucune mission n'est active actuellement au sein du Royaume.")
            return
        msg = "⚜️ **MISSIONS EN COURS DANS LE ROYAUME** ⚜️\n\n"
        vus = set()
        for j_id, m in missions_actives.items():
            if id(m) in vus: continue
            vus.add(id(m))
            
            maintenant = datetime.now()
            tot = m["duree_totale"].total_seconds()
            rest = (m["date_fin"] - maintenant).total_seconds()
            pct = max(0.0, min(1.0, (tot - rest) / tot)) if tot > 0 else 1.0
            nb_blocs = int(pct * 10)
            barre = "▓" * nb_blocs + "░" * (10 - nb_blocs)
            
            t_restant = m["date_fin"] - maintenant
            jours = t_restant.days
            heures, reste = divmod(t_restant.seconds, 3600)
            minutes, _ = divmod(reste, 60)
            
            membres_txt = ", ".join([f"<@{uid}>" for uid in m["membres"]])
            type_mission = "👥 GROUPE" if len(m["membres"]) > 1 else "👤 SOLO"
            
            msg += f"{type_mission} — {membres_txt} [**{m['cat'].upper()}**]\n📜 *\"{m['texte']}\"*\n⏱️ `[{barre}]` Reste : `{jours}j {heures}h {minutes}m`\n\n"
        await message.channel.send(msg[:2000])
        return

    if content_lower.startswith("!profil"):
        cible = message.author
        if message.mentions: cible = message.mentions[0]
        profils = charger_profils()
        initialiser_profil(cible.id, profils)
        stats = profils[str(cible.id)]
        
        reus = sum(stats["reussies"].values())
        eche = sum(stats["echouees"].values())
        total = reus + eche
        tx = int((reus / total) * 100) if total > 0 else 100
        rang = calculer_rang(stats)
        
        embed = discord.Embed(title=f"⚜️ PROFIL DE {cible.display_name.upper()} ⚜️", color=discord.Color.blue())
        embed.add_field(name="🎖️ Rang", value=f"**{rang}**", inline=False)
        embed.add_field(name="📈 Taux de Réussite", value=f"`{tx}%` ({reus} Réussies / {eche} Échouées)", inline=False)
        embed.add_field(name="📊 Détails des victoires", value=f"🟢 Comm.: `{stats['reussies']['commune']}` | 🔵 Moy.: `{stats['reussies']['moyenne']}`\n🟠 Diff.: `{stats['reussies']['difficile']}` | 👑 Royal: `{stats['reussies']['royal']}`", inline=False)
        await message.channel.send(embed=embed)
        return

    if content_lower.startswith("!historique"):
        profils = charger_profils()
        initialiser_profil(message.author.id, profils)
        hist = profils[str(message.author.id)]["historique"]
        if not font:
            await message.channel.send("📜 Votre historique est encore vierge de tous services.")
            return
        msg = f"📜 **HISTORIQUE DES ORDRES DE {message.author.display_name.upper()}** 📜\n\n"
        for x in hist:
            icon = "✅" if x["statut"] == "Succès" else "❌"
            msg += f"{icon} `[{x['date']}]` *\"{x['texte']}\"* -> **{x['statut']}**\n"
        await message.channel.send(msg)
        return

    if content_lower == "!stats_royaume":
        profils = charger_profils()
        t_reus, t_eche, max_act, top_user = 0, 0, 0, "Aucun"
        for u_id, st in profils.items():
            u_r = sum(st["reussies"].values())
            u_e = sum(st["echouees"].values())
            t_reus += u_r
            t_eche += u_e
            if (u_r + u_e) > max_act:
                max_act = (u_r + u_e)
                top_user = f"<@{u_id}>"
        
        t_tot = t_reus + t_eche
        t_tx = int((t_reus / t_tot) * 100) if t_tot > 0 else 100
        
        embed = discord.Embed(title="⚜️ ARCHIVES ADMINISTRATIVES ET STATISTIQUES ⚜️", color=discord.Color.dark_gold())
        embed.add_field(name="🌍 Total de Missions Lancées", value=f"`{t_tot}` décrets", inline=True)
        embed.add_field(name="📈 Efficacité Générale", value=f"`{t_tx}%` de réussite globale", inline=True)
        embed.add_field(name="🏆 Citoyen le plus Actif", value=f"{top_user} avec `{max_act}` missions tentées", inline=False)
        await message.channel.send(embed=embed)
        return

    if content_lower.startswith("!missionechec"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions:
            await message.channel.send("❌ Usage : `!missionechec @joueur`")
            return
        cible = message.mentions[0]
        if cible.id in missions_actives:
            m_info = missions_actives[cible.id]
            sauvegarder_mission_fichier(m_info["cat"], m_info["texte"], m_info["delai_texte"])
            
            escouade = m_info["membres"]
            profils = charger_profils()
            for uid in escouade:
                initialiser_profil(uid, profils)
                profils[str(uid)]["echouees"][m_info["cat"]] += 1
                ajouter_historique(uid, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)
            
            mentions_membres = ", ".join([f"<@{uid}>" for uid in escouade])
            for uid in escouade:
                if uid in missions_actives: del missions_actives[uid]
                
            role_instructeur = discord.utils.get(message.guild.roles, name="Instructeur")
            if not role_instructeur:
                try: role_instructeur = await message.guild.create_role(name="Instructeur", mentionable=True, color=discord.Color.blue())
                except discord.Forbidden: role_instructeur = None
            mention_ins = role_instructeur.mention if role_instructeur else "@Instructeur"
            
            await message.channel.send(
                f"🚨 **ANNULATION SUPÉRIEURE** 🚨\nLa mission de l'escouade ({mentions_membres}) a été annulée de force par un supérieur ({message.author.mention}).\n"
                f"📢 {mention_ins} l'ordre retourne aux archives.\n\n{TEXTE_ECHEC}"
            )
        else:
            await message.channel.send("❌ Ce joueur n'est associé à aucune mission active.")
        return

    if content_lower == "!fin":
        joueur = message.author
        if joueur.id not in missions_actives:
            await message.channel.send(f"❌ {joueur.mention}, tu n'as aucune mission active en ce moment.")
            return
        role_instructeur = discord.utils.get(message.guild.roles, name="Instructeur")
        m_info = missions_actives[joueur.id]
        
        is_groupe = len(m_info["membres"]) > 1
        txt_groupe = "L'escouade " + ", ".join([f"<@{uid}>" for uid in m_info["membres"]]) if is_groupe else joueur.mention
        
        await message.channel.send(f"📢 {role_instructeur.mention if role_instructeur else '@Instructeur'} ! {txt_groupe} déclare avoir fini : *\"{m_info['texte']}\"* !")
        return

    if content_lower.startswith("!missionfinit"):
        if not message.author.guild_permissions.administrator: return
        if not message.mentions: return
        cible = message.mentions[0]
        if cible.id in missions_actives:
            m_info = missions_actives[cible.id]
            escouade = m_info["membres"]
            
            profils = charger_profils()
            for uid in escouade:
                initialiser_profil(uid, profils)
                profils[str(uid)]["reussies"][m_info["cat"]] += 1
                ajouter_historique(uid, profils, m_info["texte"], "Succès")
            sauvegarder_profils(profils)
            
            mentions_membres = ", ".join([f"<@{uid}>" for uid in escouade])
            for uid in escouade:
                if uid in missions_actives: del missions_actives[uid]
                
            await message.channel.send(f"✅ Mission de l'escouade ({mentions_membres}) validée et enregistrée !")
        else:
            await message.channel.send(f"❌ Aucune mission active pour ce joueur.")
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

    if content_lower.startswith("!mission_groupe"):
        mots = content_lower.split()
        if len(mots) < 3:
            await message.channel.send("❌ Usage : `!mission_groupe <difficulté> @joueur1 @joueur2 ...`")
            return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        else: return

        # Création de l'escouade : l'auteur + les mentions
        escouade = [message.author.id]
        for m in message.mentions:
            if m.id not in escouade and not m.bot:
                escouade.append(m.id)

        if len(escouade) < 2:
            await message.channel.send("❌ Tu dois mentionner au moins un autre joueur pour fonder une escouade.")
            return

        # Vérification qu'aucun membre n'est déjà occupé
        occupes = [f"<@{uid}>" for uid in escouade if uid in missions_actives]
        if occupes:
            await message.channel.send(f"❌ Impossible de lancer : {', '.join(occupes)} participe(nt) déjà à un décret.")
            return

        missions_dispo = charger_missions_fichier()
        if not missions_dispo[cat]:
            await message.channel.send(f"⚪ Aucune mission **{cat}** disponible dans les réserves.")
            return

        index_choisi = random.randint(0, len(missions_dispo[cat]) - 1)
        mission_choisie = missions_dispo[cat].pop(index_choisi)
        réécrire_toutes_missions(missions_dispo)

        duree_calculee = extraire_duree(mission_choisie["delai"])
        maintenant_debut = datetime.now()
        date_limite = maintenant_debut + duree_calculee

        m_data = {
            "texte": mission_choisie["texte"],
            "delai_texte": mission_choisie["delai"],
            "date_debut": maintenant_debut,
            "date_fin": date_limite,
            "duree_totale": duree_calculee,
            "cat": cat,
            "channel_id": message.channel.id,
            "alerte_moitie": False,
            "alerte_un_quart": False,
            "membres": escouade
        }

        # On lie la même référence de dictionnaire à chaque membre
        for uid in escouade:
            missions_actives[uid] = m_data

        mentions_membres = ", ".join([f"<@{uid}>" for uid in escouade])
        await message.channel.send(f"👥 **Mission de groupe assignée à {mentions_membres} !**\n📜 *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
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
            "alerte_un_quart": False,
            "membres": [joueur.id]
        }
        
        await message.channel.send(f"Mission : *\"{mission_choisie['texte']}\"* (Délai : {mission_choisie['delai']})")
        return

keep_alive()
bot.run(os.environ.get("DISCORD_TOKEN", "TON_TOKEN_ICI"))

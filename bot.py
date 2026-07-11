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

def verifier_permissions_staff(user):
    roles_noms = [r.name for r in user.roles]
    return user.guild_permissions.administrator or "[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]" in roles_noms or "Palais Royal" in roles_noms

async def envoyer_double_notification(guild, msg_ticket, msg_missions, view=None):
    # Changement effectué ici pour cibler le salon "validation-mission"
    salon_missions = discord.utils.get(guild.text_channels, name="validation-mission")
    if salon_missions:
        try: await salon_missions.send(msg_missions, view=view)
        except: pass

class VueFermerTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="btn_fermer_ticket")
    async def fermer_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ Suppression du salon en cours...", ephemeral=True)
        try: await interaction.channel.delete()
        except: pass

async def action_accepter_mission(joueur_id, channel):
    if joueur_id in missions_actives:
        m_info = missions_actives[joueur_id]
        profils = charger_profils()
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_reussies"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Succès")
        sauvegarder_profils(profils)
        del missions_actives[joueur_id]
        
        msg = "✅ **Mission Validée** ! L'objectif est consigné comme réussi dans le grand registre."
        await channel.send(msg, view=VueFermerTicket())
        await envoyer_double_notification(channel.guild, msg, f"✅ **Mission accomplie** par <@{joueur_id}> : *\"{m_info['texte']}\"*")
        return True
    return False

async def action_refuser_mission(joueur_id, channel):
    if joueur_id in missions_actives:
        m_info = missions_actives[joueur_id]
        profils = charger_profils()
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_echouees"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
        sauvegarder_profils(profils)
        del missions_actives[joueur_id]
        
        msg = f"↩️ **Mission Terminée (Refusé/Échec)**.\n\n{TEXTE_ECHEC}"
        await channel.send(msg, view=VueFermerTicket())
        await envoyer_double_notification(channel.guild, msg, f"❌ **Mission échouée/refusée** pour <@{joueur_id}> : *\"{m_info['texte']}\"*")
        return True
    return False

async def action_demander_preuve(joueur_id, channel, guild):
    if joueur_id in missions_actives:
        member = guild.get_member(joueur_id)
        if member:
            await channel.set_permissions(member, read_messages=True, send_messages=True)
            
        role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]"
        
        msg_ticket = f"⚠️ <@{joueur_id}>, **{mention_ins} veuillez nous fournire une preuve de l'acomplissement de votre mission**"
        msg_log_missions = f"📸 {mention_ins} — Une demande de preuve a été envoyée à <@{joueur_id}> dans son ticket {channel.mention}."
        
        await channel.send(msg_ticket)
        await envoyer_double_notification(guild, msg_ticket, msg_log_missions)
        return True
    return False

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
            profils = charger_profils()
            initialiser_profil(joueur_id, profils)
            profils[str(joueur_id)]["total_echouees"] += 1
            ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
            sauvegarder_profils(profils)

            role_instructeur = discord.utils.get(channel.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
            mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]'
            
            msg_echec = (
                f"🚨 **MISSION ÉCHOUÉE** 🚨\nLe temps imparti est écoulé ! La mission de <@{joueur_id}> a échoué.\n"
                f"📢 {mention_ins}, un citoyen a failli à son devoir.\n\n{TEXTE_ECHEC}"
            )
            await channel.send(msg_echec, view=VueFermerTicket())
            await envoyer_double_notification(channel.guild, msg_echec, f"🚨 <@{joueur_id}> a dépassé le temps imparti pour sa mission : *\"{m_info['texte']}\"* !")
            
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

class VueBoutonTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un Ticket de Mission", style=discord.ButtonStyle.green, custom_id="btn_ouvrir_ticket")
    async def ouvrir_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        joueur = interaction.user
        
        nom_categorie_requis = "⚜️ == [ 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 ] =="
        if not interaction.channel.category or interaction.channel.category.name != nom_categorie_requis:
            await interaction.response.send_message(f"❌ Les tickets s'ouvrent uniquement dans les salons de la catégorie **{nom_categorie_requis}** !", ephemeral=True)
            return
        
        if joueur.id in missions_actives:
            await interaction.response.send_message("Vous ne pouvez obtenir qu'une seule mission a la fois !", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        role_palais = discord.utils.get(guild.roles, name="Palais Royal")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            joueur: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if role_instructeur: overwrites[role_instructeur] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if role_palais: overwrites[role_palais] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        nom_salon = f"🪖-ordre-{joueur.name}"
        ticket_channel = await guild.create_text_channel(name=nom_salon, overwrites=overwrites, category=interaction.channel.category)
        
        mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]"
        msg_notif = f"⚔️ {mention_ins} — Un nouveau ticket d'ordre vient d'être initié par {joueur.mention} dans {ticket_channel.mention} !"
        await envoyer_double_notification(guild, msg_notif, msg_notif)

        embed_ticket = discord.Embed(
            title="⚜️ CENTRE DE SÉLECTION DES DÉCRETS ⚜️",
            description=f"Bienvenue {joueur.mention}.\nChoisis la difficulté de l'objectif que tu souhaites accomplir aujourd'hui pour Madagascar.",
            color=discord.Color.dark_red()
        )
        await ticket_channel.send(embed=embed_ticket, view=VueChoixDifficulte(joueur.id))
        await interaction.followup.send(f"✅ Ton ticket a été créé ici : {ticket_channel.mention}", ephemeral=True)

class VueChoixDifficulte(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=600)
        self.joueur_id = joueur_id

    async def attribuer_mission_bouton(self, interaction: discord.Interaction, cat: str):
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message("❌ Ce ticket ne t'appartient pas.", ephemeral=True)
            return
            
        if self.joueur_id in missions_actives:
            await interaction.response.send_message("Vous ne pouvez obtenir qu'une seule mission a la fois !", ephemeral=True)
            return

        global missions_dispo
        missions_dispo = charger_missions_fichier()
        if not missions_dispo[cat]:
            await interaction.response.send_message(f"❌ Plus de mission disponible dans la catégorie `{cat.upper()}`.", ephemeral=True)
            return

        mission_choisie = random.choice(missions_dispo[cat])

        duree = extraire_duree(mission_choisie["delai"])
        date_fin = datetime.now() + duree
        timestamp_discord = int(date_fin.timestamp())

        missions_actives[self.joueur_id] = {
            "texte": mission_choisie["texte"], "delai_texte": mission_choisie["delai"],
            "date_debut": datetime.now(), "date_fin": date_fin, "duree_totale": duree,
            "cat": cat, "channel_id": interaction.channel.id, "alerte_moitie": False, "alerte_un_quart": False, "en_attente": False
        }

        for child in self.children:
            child.disabled = True

        embed_mission = discord.Embed(title="📜 DECRET ATTRIBUÉ ET CHRONO LANCÉ", color=discord.Color.gold())
        embed_mission.add_field(name="🎯 Objectif", value=f"*{mission_choisie['texte']}*", inline=False)
        embed_mission.add_field(name="⏳ Temps restant réel", value=f"<t:{timestamp_discord}:R> (soit le <t:{timestamp_discord}:f>)", inline=False)
        
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(content=f"{interaction.user.mention}", embed=embed_mission, view=VueGestionJoueurMission(self.joueur_id))

    @discord.ui.button(label="🟢 Commune", style=discord.ButtonStyle.secondary, custom_id="btn_commune")
    async def btn_commune(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "commune")

    @discord.ui.button(label="🔵 Moyenne", style=discord.ButtonStyle.primary, custom_id="btn_moyenne")
    async def btn_moyenne(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "moyenne")

    @discord.ui.button(label="🟠 Difficile", style=discord.ButtonStyle.success, custom_id="btn_difficile")
    async def btn_difficile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "difficile")

    @discord.ui.button(label="🔴 Royal", style=discord.ButtonStyle.danger, custom_id="btn_royal")
    async def btn_royal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "royal")

class VueGestionJoueurMission(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="🏁 Finir la mission", style=discord.ButtonStyle.success, custom_id="joueur_finir_mission")
    async def joueur_finir(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message("❌ Cet objectif ne t'appartient pas.", ephemeral=True)
            return

        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Tu n'as aucune mission active.", ephemeral=True)
            return

        m_info = missions_actives[self.joueur_id]
        if not m_info.get("en_attente", False):
            m_info["en_attente"] = True
            m_info["moment_gel"] = datetime.now()

        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)

        role_instructeur = discord.utils.get(interaction.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]'

        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=False)
        await interaction.channel.send(f"💬 {interaction.user.mention}, un instructeur a été notifié. Votre demande va être traitée dans les plus brefs délais.")
        
        msg_fin = (
            f"📢 {mention_ins} ! {interaction.user.mention} déclare avoir fini sa mission via l'interface : *\"{m_info['texte']}\"* !\n"
            f"⏱️ **Le chrono est mis en pause.** Choisissez l'action appropriée :"
        )
        await envoyer_double_notification(interaction.guild, msg_fin, f"📢 {mention_ins} — <@{self.joueur_id}> demande une validation pour : *\"{m_info['texte']}\"* dans {interaction.channel.mention}", view=VueEvaluationMission(self.joueur_id))

    @discord.ui.button(label="❌ Abandonner", style=discord.ButtonStyle.danger, custom_id="joueur_abandonner_mission")
    async def joueur_abandonner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message("❌ Tu ne peux pas abandonner la mission de quelqu'un d'autre.", ephemeral=True)
            return

        if self.joueur_id not in missions_actives:
            await interaction.response.send_message("❌ Tu n'as pas de mission active à abandonner.", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)
        await action_refuser_mission(self.joueur_id, interaction.channel)

class VueEvaluationMission(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="eval_accepter")
    async def eval_accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu n'as pas l'autorité nécessaire pour évaluer cet ordre.", ephemeral=True)
            return
        
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)
        
        m_info = missions_actives.get(self.joueur_id)
        chan_cible = bot.get_channel(m_info["channel_id"]) if m_info else interaction.channel
        await action_accepter_mission(self.joueur_id, chan_cible)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="eval_refuser")
    async def eval_refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu n'as pas l'autorité nécessaire pour évaluer cet ordre.", ephemeral=True)
            return
        
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)
        
        m_info = missions_actives.get(self.joueur_id)
        chan_cible = bot.get_channel(m_info["channel_id"]) if m_info else interaction.channel
        await action_refuser_mission(self.joueur_id, chan_cible)

    @discord.ui.button(label="📸 Demander des preuves", style=discord.ButtonStyle.primary, custom_id="eval_preuve")
    async def eval_preuve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu n'as pas l'autorité nécessaire.", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        await interaction.response.edit_message(view=self)
        
        m_info = missions_actives.get(self.joueur_id)
        chan_cible = bot.get_channel(m_info["channel_id"]) if m_info else interaction.channel
        await action_demander_preuve(self.joueur_id, chan_cible, interaction.guild)

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    bot.add_view(VueBoutonTicket())
    bot.add_view(VueFermerTicket())
    print("Bot MADAmission Pro — Prêt et vérifié !")

@bot.event
async def on_message(message):
    global missions_dispo
    if message.author.bot: return
    content = message.content.strip()
    content_lower = content.lower()

    if message.channel.name and "🪖-ordre-" in message.channel.name and message.attachments:
        joueur_id = message.author.id
        if joueur_id in missions_actives and missions_actives[joueur_id].get("en_attente", False):
            await message.channel.send(f"💬 {message.author.mention}, un instructeur a été ping. Votre demande a bien été envoyée et va être traitée.")
            
            msg_p = f"📸 **Preuve reçue** pour la mission de <@{joueur_id}>. En attente de l'analyse finale de l'administration :"
            await envoyer_double_notification(message.guild, msg_p, f"📸 Preuve d'accomplissement déposée par <@{joueur_id}> dans {message.channel.mention}.", view=VueEvaluationMission(joueur_id))

    if content_lower in ["!aide", "!help"]:
        embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES DE MADAGASCAR ⚜️", color=discord.Color.gold())
        
        citoyen_desc = (
            "⚔️ **SYSTÈME DE QUÊTES**\n"
            "Clique sur le bouton ci-dessous pour ouvrir un salon de quête privé.\n\n"
            "`!missionacomplis` ou via les boutons sous ton chrono.\n\n"
            "`!missions_en_cours`\n↳ Affiche le statut complet de ta tâche active.\n\n"
            "📊 **ARCHIVES PERSONNELLES**\n"
            "`!historique [@joueur]`\n↳ Consultez votre bilan d'objectifs personnels."
        )
        embed.add_field(name="👥 ESPACE DES CITOYENS", value=citoyen_desc, inline=False)
        
        if verifier_permissions_staff(message.author):
            admin_desc = (
                "🚨 **HAUT COMMANDEMENT (ADMIN / INSTRUCTEUR)**\n"
                "`!missionaccepter @joueur` ↳ Valide la mission manuellement.\n"
                "`!missionrefuser @joueur`  ↳ Annule la mission avec échec.\n"
                "`!missionpreuve @joueur`   ↳ Débloque le salon et exige un screen.\n\n"
                "📂 **BASE DE DONNÉES DES MISSIONS**\n"
                "`!listemissions` | `!addmission` | `!delmission`"
            )
            embed.add_field(name="👑 ADMINISTRATION", value=admin_desc, inline=False)
            
        await message.channel.send(embed=embed, view=VueBoutonTicket())
        return

    # --- COMMANDES MANUELLES STAFF ---

    if content_lower.startswith("!missionaccepter"):
        if not verifier_permissions_staff(message.author): return
        if not message.mentions:
            await message.channel.send("❌ Format incorrect. Exemple : `!missionaccepter @joueur`")
            return
        cible = message.mentions[0]
        reussite = await action_accepter_mission(cible.id, message.channel)
        if not reussite: await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
        return

    if content_lower.startswith("!missionrefuser"):
        if not verifier_permissions_staff(message.author): return
        if not message.mentions:
            await message.channel.send("❌ Format incorrect. Exemple : `!missionrefuser @joueur`")
            return
        cible = message.mentions[0]
        reussite = await action_refuser_mission(cible.id, message.channel)
        if not reussite: await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
        return

    if content_lower.startswith("!missionpreuve"):
        if not verifier_permissions_staff(message.author): return
        if not message.mentions:
            await message.channel.send("❌ Format incorrect. Exemple : `!missionpreuve @joueur`")
            return
        cible = message.mentions[0]
        reussite = await action_demander_preuve(cible.id, message.channel, message.guild)
        if not reussite: await message.channel.send("❌ Aucun objectif en cours trouvé pour ce joueur.")
        return

    # --- COMMANDES DE BASE ---

    if content_lower == "!missions_en_cours":
        if message.author.id not in missions_actives:
            await message.channel.send("⚪ Tu n'as aucune mission active actuellement.")
            return
            
        m = missions_actives[message.author.id]
        ts = int(m["date_fin"].timestamp())
        
        if m.get("en_attente", False):
            await message.channel.send(f"👤 <@{message.author.id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* 🛑 **GELÉ (En attente d'évaluation)**")
        else:
            await message.channel.send(f"👤 <@{message.author.id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* Fin : <t:{ts}:R>")
        return

    if content_lower == "!missionacomplis":
        joueur = message.author
        role_instructeur = discord.utils.get(message.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]")
        mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝔱𝔢𝔲𝔯 ]'
        
        if joueur.id in missions_actives:
            m_info = missions_actives[joueur.id]
            if not m_info.get("en_attente", False):
                m_info["en_attente"] = True
                m_info["moment_gel"] = datetime.now()
                
            await message.channel.set_permissions(joueur, read_messages=True, send_messages=False)
            await message.channel.send(f"💬 {joueur.mention}, un instructeur a été notifié. Votre demande va être traitée dans les plus brefs délais.")
            
            msg_comp = (
                f"📢 {mention_ins} ! {joueur.mention} déclare avoir fini sa mission : *\"{m_info['texte']}\"* !\n"
                f"⏱️ **Le chrono est mis en pause.** Choisissez l'action appropriée :"
            )
            await envoyer_double_notification(message.guild, msg_comp, f"📢 {mention_ins} — <@{joueur.id}> a fini sa mission : *\"{m_info['texte']}\"* dans {message.channel.mention}", view=VueEvaluationMission(joueur.id))
            return
            
        await message.channel.send("❌ Tu n'as aucune mission active en cours.")
        return

    if content_lower.startswith("!listemissions"):
        if not verifier_permissions_staff(message.author): return
        missions_dispo = charger_missions_fichier()
        reponse = "⚜️ **ARCHIVES DES MISSIONS DISPONIBLES** ⚜️\n"
        for cat in ["commune", "moyenne", "difficile", "royal"]:
            reponse += f"\n__**{cat.upper()} :**__\n"
            if not missions_dispo[cat]: reponse += "*Aucune mission disponible*\n"
            else:
                for i, m in enumerate(missions_dispo[cat], start=1): reponse += f"**{i}.** {m['texte']} *(Délai d'origine : {m['delai']})*\n"
        await message.channel.send(reponse[:2000])
        return

    if content_lower.startswith("!addmission"):
        if not verifier_permissions_staff(message.author): return
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

    if content_lower.startswith("!delmission"):
        if not verifier_permissions_staff(message.author): return
        mots = content_lower.split()
        if len(mots) < 3: 
            await message.channel.send("❌ Format incorrect. Exemple : `!delmission commune 1`")
            return
        cat = mots[1]
        if cat in ["commune", "commun"]: cat = "commune"
        elif cat in ["moyenne", "moyen"]: cat = "moyenne"
        elif cat in ["difficile"]: cat = "difficile"
        elif cat in ["royal", "royale"]: cat = "royal"
        try: numero = int(mots[2]) - 1
        except ValueError: 
            await message.channel.send("❌ Numéro de mission invalide.")
            return
        missions_dispo = charger_missions_fichier()
        if cat in missions_dispo and 0 <= numero < len(missions_dispo[cat]):
            retiree = missions_dispo[cat].pop(numero)
            réécrire_toutes_missions(missions_dispo)
            await message.channel.send(f"🗑️ Mission *\"{retiree['texte']}\"* supprimée avec succès.")
        else:
            await message.channel.send("❌ Numéro invalide ou mission introuvable.")
        return

    if content_lower.startswith("!historique"):
        cible = message.mentions[0] if message.mentions else message.author
        profils = charger_profils()
        initialiser_profil(cible.id, profils)
        
        userData = profils[str(cible.id)]
        hist = userData["historique"]
        
        embed = discord.Embed(title=f"📜 ARCHIVES ET PARCHEMIN — {cible.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=cible.display_avatar.url)
        
        cpt_txt = f"🟢 **Missions RÉUSSITES :** `{userData['total_reussies']}`\n🔴 **Missions ÉCHOUÉES :** `{userData['total_echouees']}`"
        embed.add_field(name="📊 Bilan des Objectifs", value=cpt_txt, inline=False)
        
        if not hist:
            embed.add_field(name="📜 Historique des Décrets", value="*Aucune mission enregistrée dans le grand registre.*", inline=False)
        else:
            hist_lignes = [("✅" if item["statut"] == "Succès" else "❌") + f" **[{item['date']}]** — {item['texte']}" for item in hist]
            corps_historique = "\n".join(hist_lignes)
            if len(corps_historique) > 1024: corps_historique = corps_historique[:1000] + "\n*...*"
            embed.add_field(name="📜 Historique des Décrets", value=corps_historique, inline=False)
            
        await message.channel.send(embed=embed)
        return

keep_alive()
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Erreur : Aucun token Discord trouvé.")

"""
Complete Team Database - ALL Clubs
Bundesliga (18), Premier League (20), La Liga (20), Serie A (20), Ligue 1 (18)
"""

# BUNDESLIGA (18 Vereine)
BUNDESLIGA_TEAMS = {
    'Bayern Munich': ['Harry Kane', 'Jamal Musiala', 'Manuel Neuer'],
    'Bayer Leverkusen': ['Florian Wirtz', 'Victor Boniface', 'Jeremie Frimpong'],
    'Borussia Dortmund': ['Serhou Guirassy', 'Julian Brandt', 'Emre Can'],
    'RB Leipzig': ['Lois Openda', 'Xavi Simons', 'Willi Orban'],
    'Eintracht Frankfurt': ['Omar Marmoush', 'Hugo Ekitike', 'Kevin Trapp'],
    'VfB Stuttgart': ['Enzo Millot', 'Deniz Undav', 'Ermedin Demirovic'],
    'SC Freiburg': ['Vincenzo Grifo', 'Ritsu Doan', 'Christian Gunter'],
    'Wolfsburg': ['Jonas Wind', 'Lovro Majer', 'Maximilian Arnold'],
    'Mainz 05': ['Jonathan Burkardt', 'Lee Jae-sung', 'Edimilson Fernandes'],
    'Hoffenheim': ['Andrej Kramaric', 'Maximilian Beier', 'Florian Grillitsch'],
    'Werder Bremen': ['Marvin Ducksch', 'Romano Schmid', 'Jens Stage'],
    'Bochum': ['Takuma Asano', 'Philipp Hofmann', 'Kevin Stoger'],
    'Heidenheim': ['Tim Kleindienst', 'Beste', 'Jan Schoppner'],
    'Union Berlin': ['Benedict Hollerbach', 'Kevin Volland', 'Rani Khedira'],
    'Augsburg': ['Ermedin Demirovic', 'Ruben Vargas', 'Felix Uduokhai'],
    'Borussia Monchengladbach': ['Alassane Plea', 'Jordan', 'Ko Itakura'],
    'St Pauli': ['Johansson', 'Jackson Irvine', 'Manolis Saliakas'],
    'Holstein Kiel': ['Fiete Arp', 'Lewis Holtby', 'Steven Skrzybski'],
}

# PREMIER LEAGUE (20 Vereine)
PREMIER_LEAGUE_TEAMS = {
    'Man City': ['Erling Haaland', 'Phil Foden', 'Kevin De Bruyne'],
    'Arsenal': ['Bukayo Saka', 'Martin Odegaard', 'Declan Rice'],
    'Liverpool': ['Mohamed Salah', 'Darwin Nunez', 'Virgil van Dijk'],
    'Aston Villa': ['Ollie Watkins', 'John McGinn', 'Emiliano Martinez'],
    'Tottenham': ['Son Heung-min', 'James Maddison', 'Dejan Kulusevski'],
    'Chelsea': ['Nicolas Jackson', 'Cole Palmer', 'Enzo Fernandez'],
    'Man United': ['Bruno Fernandes', 'Rasmus Hojlund', 'Alejandro Garnacho'],
    'Newcastle': ['Alexander Isak', 'Anthony Gordon', 'Bruno Guimaraes'],
    'Brighton': ['Danny Welbeck', 'Kaoru Mitoma', 'Billy Gilmour'],
    'West Ham': ['Jarrod Bowen', 'Lucas Paqueta', 'Edson Alvarez'],
    'Crystal Palace': ['Eberechi Eze', 'Michael Olise', 'Joachim Andersen'],
    'Brentford': ['Ivan Toney', 'Bryan Mbeumo', 'Yoane Wissa'],
    'Fulham': ['Raul Jimenez', 'Willian', 'Joao Palhinha'],
    'Everton': ['Dominic Calvert-Lewin', 'Dwight McNeil', 'Jordan Pickford'],
    'Bournemouth': ['Dominic Solanke', 'Jefferson Lerma', 'Illia Zabarnyi'],
    'Wolves': ['Hwang Hee-chan', 'Pedro Neto', 'Mario Lemina'],
    'Nottingham Forest': ['Taiwo Awoniyi', 'Morgan Gibbs-White', 'Chris Wood'],
    'Burnley': ['Lyle Foster', 'Josh Brownhill', 'Zeki Amdouni'],
    'Sheffield United': ['Oli McBurnie', 'Gustavo Hamer', 'James McAtee'],
    'Luton Town': ['Jerrod Morris', 'Carlton Morris', 'Pelly-Ruddock Mpanzu'],
}

# LA LIGA (20 Vereine)
LA_LIGA_TEAMS = {
    'Real Madrid': ['Kylian Mbappe', 'Vinicius Jr', 'Jude Bellingham'],
    'Barcelona': ['Robert Lewandowski', 'Lamine Yamal', 'Pedri'],
    'Atletico Madrid': ['Antoine Griezmann', 'Julian Alvarez', 'Jan Oblak'],
    'Girona': ['Artem Dovbyk', 'Savio Moreira', 'Aleix Garcia'],
    'Athletic Bilbao': ['Inaki Williams', 'Nico Williams', 'Oihan Sancet'],
    'Real Sociedad': ['Mikel Oyarzabal', 'Takefusa Kubo', 'Martin Zubimendi'],
    'Real Betis': ['Willian Jose', 'Isco', 'Borja Iglesias'],
    'Sevilla': ['En-Nesyri', 'Lucas Ocampos', 'Ivan Rakitic'],
    'Valencia': ['Hugo Duro', 'Mouctar Diakhaby', 'Diego Lopez'],
    'Villarreal': ['Gerard Moreno', 'Alexander Sorloth', 'Dani Parejo'],
    'Las Palmas': ['Munir', 'Kirian Rodriguez', 'Sandro Ramirez'],
    'Alaves': ['Rioja', 'Jon Guridi', 'Alex Sola'],
    'Osasuna': ['Budimir', 'Aimar Oroz', 'Ruben Garcia'],
    'Getafe': ['Borja Mayoral', 'Mason Greenwood', 'Carles Alena'],
    'Rayo Vallecano': ['Jorge de Frutos', 'Alvaro Garcia', 'Oscar Trejo'],
    'Celta Vigo': ['Jorgen Strand Larsen', 'Iago Aspas', 'Vicente Guaita'],
    'Mallorca': ['Vedat Muriqi', 'Antonio Raillo', 'Dani Rodriguez'],
    'Cadiz': ['Chris Ramos', 'Roger Marti', 'Lucas Pires'],
    'Granada': ['Myrto Uzuni', 'Lucas Boye', 'Ricardo Sanchez'],
    'Almeria': ['Luis Suarez', 'Bilal Toure', 'Gonzalo Melero'],
}

# SERIE A (20 Vereine)
SERIE_A_TEAMS = {
    'Inter': ['Lautaro Martinez', 'Marcus Thuram', 'Hakan Calhanoglu'],
    'Juventus': ['Dusan Vlahovic', 'Kenan Yildiz', 'Federico Chiesa'],
    'Milan': ['Rafael Leao', 'Christian Pulisic', 'Mike Maignan'],
    'Bologna': ['Riccardo Orsolini', 'Joshua Zirkzee', 'Lewis Ferguson'],
    'Roma': ['Romelu Lukaku', 'Paulo Dybala', 'Lorenzo Pellegrini'],
    'Atalanta': ['Ademola Lookman', 'Charles De Ketelaere', 'Marten de Roon'],
    'Napoli': ['Victor Osimhen', 'Khvicha Kvaratskhelia', 'Giovanni Di Lorenzo'],
    'Lazio': ['Ciro Immobile', 'Luis Alberto', 'Mattia Zaccagni'],
    'Fiorentina': ['Nicolas Gonzalez', 'Lucas Beltran', 'Rolando Mandragora'],
    'Torino': ['Duvan Zapata', 'Antonio Sanabria', 'Samuele Ricci'],
    'Monza': ['Andrea Colpani', 'Dany Mota', 'Michele Di Gregorio'],
    'Genoa': ['Albert Gudmundsson', 'Mateo Retegui', 'Alberto Gilardino'],
    'Sassuolo': ['Andrea Pinamonti', 'Domenico Berardi', 'Kristian Thorstvedt'],
    'Udinese': ['Lorenzo Lucca', 'Florian Thauvin', 'Gerard Deulofeu'],
    'Lecce': ['Nikola Krstovic', 'Remi Oudin', 'Santiago Pierotti'],
    'Empoli': ['Alberto Cerri', 'Mbaye Niang', 'Nicolò Cambiaghi'],
    'Verona': ['Milan Djuric', 'Darko Lazovic', 'Federico Bonazzoli'],
    'Cagliari': ['Gianluca Lapadula', 'Leonardo Pavoletti', 'Nahitan Nandez'],
    'Frosinone': ['Matias Soule', 'Walid Cheddira', 'Marco Brescianini'],
    'Salernitana': ['Simone Verdi', 'Toni Vilhena', 'Federico Fazio'],
}

# LIGUE 1 (18 Vereine)
LIGUE_1_TEAMS = {
    'PSG': ['Kylian Mbappe', 'Ousmane Dembele', 'Bradley Barcola'],
    'Monaco': ['Wissam Ben Yedder', 'Takumi Minamino', 'Denis Zakaria'],
    'Marseille': ['Pierre-Emerick Aubameyang', 'Mason Greenwood', 'Leonardo Balerdi'],
    'Lille': ['Jonathan David', 'Yusuf Yazici', 'Leny Yoro'],
    'Rennes': ['Martin Terrier', 'Ludovic Blas', 'Amine Gouiri'],
    'Lyon': ['Alexandre Lacazette', 'Rayan Cherki', 'Maxence Caqueret'],
    'Lens': ['Florin Sotoca', 'Elye Wahi', 'Angelo Fulgini'],
    'Strasbourg': ['Emegha', 'Dilane Bakwa', 'Jeremy Sebas'],
    'Nantes': ['Mostafa Mohamed', 'Moses Simon', 'Pedro Chirivella'],
    'Reims': ['Junya Ito', 'Teddy Teuma', 'Marshall Munetsi'],
    'Toulouse': ['Thijs Dallinga', 'Vincent Sierro', 'Moussa Diarra'],
    'Montpellier': ['Wahbi Khazri', 'Teji Savanier', 'Mamadou Sakho'],
    'Nice': ['Terem Moffi', 'Jeremie Boga', 'Khephren Thuram'],
    'Le Havre': ['Nabil Alioui', 'Gautier Lloris', 'Samuel Grandsir'],
    'Brest': ['Steve Mounie', 'Pierre Lees-Melou', 'Mathias Pereira Lage'],
    'Metz': ['Georges Mikautadze', 'Pape Diallo', 'Lamine Camara'],
    'Lorient': ['Eli Junior Kroupi', 'Ahmadou Dieng', 'Adil Aouchiche'],
    'Clermont Foot': ['Muhammed Cham', 'Jim Allevinah', 'Johan Gastien'],
}

# Combined Database
ALL_TEAMS = {
    **BUNDESLIGA_TEAMS,
    **PREMIER_LEAGUE_TEAMS,
    **LA_LIGA_TEAMS,
    **SERIE_A_TEAMS,
    **LIGUE_1_TEAMS,
}

# Team → Liga Mapping
TEAM_LEAGUE_MAPPING = {team: 'D1' for team in BUNDESLIGA_TEAMS}
TEAM_LEAGUE_MAPPING.update({team: 'E0' for team in PREMIER_LEAGUE_TEAMS})
TEAM_LEAGUE_MAPPING.update({team: 'SP1' for team in LA_LIGA_TEAMS})
TEAM_LEAGUE_MAPPING.update({team: 'I1' for team in SERIE_A_TEAMS})
TEAM_LEAGUE_MAPPING.update({team: 'F1' for team in LIGUE_1_TEAMS})

# UEFA Fallback Teams (for CL/EL/Conference)
UEFA_FALLBACK_TEAMS = {
    # Portugal
    'Benfica': 'P1', 'Porto': 'P1', 'Sporting CP': 'P1', 'Braga': 'P1',
    # Austria, Turkey, Eastern Europe (Europa League regulars)
    'Salzburg': 'D1', 'Galatasaray': 'I1', 'Fenerbahce': 'I1',
    'Shakhtar Donetsk': 'SP1', 'Dynamo Kyiv': 'I1',
    'Celtic': 'E0', 'Rangers': 'E0',
}

# Add remaining fallbacks to UEFA_FALLBACK_TEAMS
UEFA_FALLBACK_TEAMS_COMPLETE = {
    'Club Brugge': 'P1',
    'Union Saint-Gilloise': 'P1',
}

# Export all mappings
ALL_TEAM_MAPPINGS = {**TEAM_LEAGUE_MAPPING, **UEFA_FALLBACK_TEAMS, **UEFA_FALLBACK_TEAMS_COMPLETE}
def get_tollbooths_osm(year: int, country_name: str):
    query = f'''
    [out:json];
    area["name"="{country_name}"]->.searchArea;
    (
    node["barrier"="toll_booth"](area.searchArea);
    );
    out center;
    '''
    response = requests.post("https://overpass-api.de/api/interpreter", data=query)
    print(response.text)
    data = response.json()

    # Parse the results into a dataframe
    tollbooths = [
        {
            "osm_id": elem.get("id"),
            "lat": elem["center"]["lat"] if "center" in elem else elem.get("lat"),
            "lng": elem["center"]["lon"] if "center" in elem else elem.get("lon"),
            "name": elem.get("tags", {}).get("name", "")
        }
        for elem in data.get("elements", [])
    ]
    return tollbooths
    
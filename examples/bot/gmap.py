class Map(object):
    def __init__(self):
        self._points1 = []
        self._points2 = []
        self._positions = []
        self._bounds = []
        self._player = None
    def add_point1(self, coordinates, icon):
        self._points1.append((coordinates, icon))
    def add_point2(self, coordinates, icon):
        self._points2.append((coordinates, icon))
    def add_position(self, coordinates):
        self._positions.append(coordinates)
    def add_bound(self, coordinates):
        self._bounds.append(coordinates)
    def __str__(self):
        centerLat = sum((x[0] for x in self._positions)) / len(self._positions)
        centerLon = sum((x[1] for x in self._positions)) / len(self._positions)
        pathCode = """
            var boundsCoords = [{bounds}];
            if (boundsCoords.length > 0) {{
                var border = new google.maps.Polyline({{
                    path: boundsCoords,
                    geodesic: true,
                    strokeColor: '#FF0000',
                    strokeOpacity: 0.5,
                    strokeWeight: 8}});
                border.setMap(map);
                var arrayLength = boundsCoords.length;
                for (var i = 0; i < arrayLength; i++) {{
                    bnds.extend(boundsCoords[i]);
                }}
            }}
            var walkPathCoords = [{path}];
            var walkPath = new google.maps.Polyline({{
                path: walkPathCoords,
                geodesic: true,
                strokeColor: '#7F00FF',
                strokeOpacity: 0.5,
                strokeWeight: 4}});
            walkPath.setMap(map);
        """.format(bounds=",".join(["new google.maps.LatLng(%f,%f)" % (p[0], p[1]) for p in self._bounds]),
                   path=",".join(["new google.maps.LatLng(%f,%f)" % (p[0], p[1]) for p in self._positions]))
        markers1Code = "\n".join(
            ["""var pos = new google.maps.LatLng({lat},{lng});
                var marker = new google.maps.Marker({{
                position: pos,
                map: map
                }});
                marker.setIcon('{icon}');
                bnds.extend(pos);""".format(lat=x[0][0], lng=x[0][1], icon=x[1]) for x in self._points1
            ])
        markers2Code = "\n".join(
            ["""var pos = new google.maps.LatLng({lat},{lng});
                var marker = new google.maps.Marker({{
                position: pos,
                map: map
                }});
                marker.setIcon(sprites[{icon}]);
                bnds.extend(pos);""".format(lat=x[0][0], lng=x[0][1], icon=x[1]) for x in self._points2
            ])
        playerCode = """var marker = new google.maps.Marker({{
                        position: {{lat: {lat}, lng: {lng}}},
                        map: map
                        }});
                        marker.setIcon('http://maps.google.com/mapfiles/ms/icons/purple.png');""".format(lat=self._player[0], lng=self._player[1])
        return """
            <script src="https://maps.googleapis.com/maps/api/js?v=3.exp&sensor=false"></script>
            <div id="map-canvas" style="height: 100%; width: 100%"></div>
            <script type="text/javascript">
                var map;
                var sprites = {{{sprites}}};
                for (var i in sprites) {{
                    sprites[i] = {{
                        url: sprites[i],
                        size: new google.maps.Size(120,120),
                        origin: new google.maps.Point(0,0),
                        anchor: new google.maps.Point(0,0),
                        scaledSize: new google.maps.Size(64,64)
                    }};
                }}
                function show_map() {{
                    map = new google.maps.Map(document.getElementById("map-canvas"), {{
                        zoom: 16,
                        center: new google.maps.LatLng({centerLat}, {centerLon})
                    }});
                    var bnds = new google.maps.LatLngBounds();
                    {pathCode}
                    {markers1Code}
                    {markers2Code}
                    {playerCode}
                    map.fitBounds(bnds);
                }}
                google.maps.event.addDomListener(window, 'load', show_map);
            </script>
        """.format(centerLat=centerLat, centerLon=centerLon,
                   pathCode=pathCode, playerCode=playerCode,
                   markers1Code=markers1Code, markers2Code=markers2Code,
                   sprites=",".join(["%03d: 'http://www.serebii.net/pokemongo/pokemon/%03d.png'" % (i,i) for i in range(1,152)]))

print('This will be the F1 Telemetry Server')

"""
F1 24 UDP Client
Handles receiving and parsing binary UDP packets from the F1 game.
Specific to F1 23/24 Packet Format (2023 Spec).
"""
import socket
import struct
import threading
import logging
from telemetry_state import state

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('F1UDP')

# Constants
UDP_IP = "0.0.0.0"
UDP_PORT = 20777
BUFFER_SIZE = 2048

# Packet IDs
PACKET_ID_SESSION      = 1
PACKET_ID_LAP_DATA     = 2
PACKET_ID_CAR_TELEMETRY = 6
PACKET_ID_CAR_STATUS   = 7

class F1PacketParser:
    """Parses binary packets from F1 24"""
    
    @staticmethod
    def parse_header(packet):
        """Parse standard 24-byte header"""
        # uint16, uint8, uint8, uint8, uint8, uint64, float, uint32, uint32, uint8, uint8
        header_fmt = '<HBBBBQfIIBB'
        header_size = struct.calcsize(header_fmt)
        
        if len(packet) < header_size:
            return None
            
        data = struct.unpack(header_fmt, packet[:header_size])
        return {
            'packet_format': data[0],  # 2023/2024
            'game_major_version': data[1],
            'game_minor_version': data[2],
            'packet_version': data[3],
            'packet_id': data[4],
            'session_uid': data[5],
            'session_time': data[6],
            'frame_identifier': data[7],
            'player_car_index': data[8]
        }

    @staticmethod
    def parse_car_telemetry(packet, player_index):
        """Parse Car Telemetry Data (ID 6)"""
        # Header is 24 bytes (29 in 2024 spec, let's assume 2023 spec for MVP compatibility)
        # But wait, header size varies by year. 
        # F1 23 Header is 29 bytes. F1 22 is 24 bytes.
        # Let's target F1 23/24 which uses 29 byte header.
        
        # Header size logic: F1 2024 uses 28/29 bytes? 
        # We use dynamic calculation from F1PacketParser.parse_header's format.
        header_fmt = '<HBBBBQfIIBB'
        header_size = struct.calcsize(header_fmt)
        
        # Each car data is 60 bytes
        # struct CarTelemetryData {
        #    uint16 m_speed;                         // Speed of car in kilometres per hour
        #    float m_throttle;                       // Amount of throttle applied (0.0 to 1.0)
        #    float m_steer;                          // Steering (-1.0 (full lock left) to 1.0 (full lock right))
        #    float m_brake;                          // Amount of brake applied (0.0 to 1.0)
        #    uint8 m_clutch;                         // Amount of clutch applied (0 to 100)
        #    int8 m_gear;                            // Gear selected (1-8, N=0, R=-1)
        #    uint16 m_engineRPM;                     // Engine RPM
        #    uint8 m_drs;                            // 0 = off, 1 = on
        #    uint8 m_revLightsPercent;               // Rev lights indicator (percentage)
        #    uint16 m_revLightsBitValue;             // Rev lights (bit 0 = leftmost LED, bit 14 = rightmost LED)
        #    uint16 m_brakesTemperature[4];          // Brakes temperature (celsius)
        #    uint8 m_tyresSurfaceTemperature[4];     // Tyres surface temperature (celsius)
        #    uint8 m_tyresInnerTemperature[4];       // Tyres inner temperature (celsius)
        #    uint16 m_engineTemperature;             // Engine temperature (celsius)
        #    float m_tyresPressure[4];               // Tyres pressure (PSI)
        #    uint8 m_surfaceType[4];                 // Driving surface type
        # }
        
        # Correct Spec: H(Speed) fff(Throt,Steer,Brake) Bb(Clutch,Gear) H(RPM) BB(DRS,Rev) H(RevBit)
        # HHHH(Brakes) BBBB(TyreSurf) BBBB(TyreInner) H(Engine) ffff(Press) BBBB(Surf)
        car_data_fmt = '<HfffBbHBBHHHHHBBBBBBBBHffffBBBB'
        car_data_size = struct.calcsize(car_data_fmt)
        
        offset = header_size + (player_index * car_data_size)
        
        if len(packet) < offset + car_data_size:
            return None
            
        data = struct.unpack(car_data_fmt, packet[offset:offset+car_data_size])
        
        # Data Indices:
        # 0-9: Header-ish
        # 10-13: Brakes
        # 14-17: Tyre Surf
        # 18-21: Tyre Inner
        # 22: Engine
        
        return {
            'speed': data[0],
            'throttle': data[1],
            'steer': data[2],
            'brake': data[3],
            'clutch': data[4],
            'gear': data[5],
            'rpm': data[6],
            'drs': data[7],
            'rev_lights_percent': data[8],
            'engine_temp': data[22],
            'tyres_surface_temp': [data[14], data[15], data[16], data[17]]
        }

    @staticmethod
    def parse_lap_data(packet, player_index):
        """Parse Lap Data (ID 2)"""
        header_fmt = '<HBBBBQfIIBB'
        header_size = struct.calcsize(header_fmt)
        
        # struct LapData {
        #    uint32 m_lastLapTimeInMS;               // Last lap time in milliseconds
        #    uint32 m_currentLapTimeInMS;            // Current time around the lap in milliseconds
        #    uint16 m_sector1TimeInMS;               // Sector 1 time in milliseconds
        #    uint16 m_sector2TimeInMS;               // Sector 2 time in milliseconds
        #    float m_lapDistance;                    // Distance vehicle is around current lap in metres
        #    float m_totalDistance;                  // Total distance travelled in session in metres -- could be negative if we haven't crossed the line yet
        #    float m_safetyCarDelta;                 // Delta in seconds for safety car
        #    uint8 m_carPosition;                    // Car race position
        #    uint8 m_currentLapNum;                  // Current lap number
        #    uint8 m_pitStatus;                      // 0 = none, 1 = pitting, 2 = in pit area
        #    uint8 m_numPitStops;                    // Number of pit stops taken in this session
        #    uint8 m_sector;                         // 0 = sector1, 1 = sector2, 2 = sector3
        #    uint8 m_currentLapInvalid;              // Current lap invalid - 0 = valid, 1 = invalid
        #    uint8 m_penalties;                      // Accumulated time penalties in seconds to be added
        #    uint8 m_warnings;                       // Accumulated number of warnings issued
        #    uint8 m_numUnservedDriveThroughPens;    // Num drive through pens left to serve
        #    uint8 m_numUnservedStopGoPens;          // Num stop go pens left to serve
        #    uint8 m_gridPosition;                   // Grid position the vehicle started the race in
        #    uint8 m_driverStatus;                   // Status of driver - 0 = in garage, 1 = flying lap, 2 = in lap, 3 = out lap, 4 = on track
        #    uint8 m_resultStatus;                   // Result status - 0 = invalid, 1 = inactive, 2 = active, 3 = finished, 4 = didnotfinish, 5 = disqualified, 6 = not classified, 7 = retired
        #    uint8 m_pitLaneTimerActive;             // Pit lane timing, 0 = inactive, 1 = active
        #    uint16 m_pitLaneTimeInLaneInMS;         // If active, the current time spent in the pit lane in ms
        #    uint16 m_pitStopTimerInMS;              // Time of the actual pit stop in ms
        #    uint8 m_pitStopShouldServePen;          // Whether the car should serve a penalty at this stop
        # }
        
        # Spec: II HH fff B(x14) HH B
        # LastLap,CurLap,S1,S2,Dist,Tot,SC
        # Pos,Lap,Pit,Stops,Sec,Inv,Pen,Warn,Drive,Stop,Grid,Driver,Result,PitActive (14)
        # PitTime,StopTime,StopPen
        lap_data_fmt = '<IIHHfffBBBBBBBBBBBBBBHHB'
        lap_data_size = struct.calcsize(lap_data_fmt)
        
        offset = header_size + (player_index * lap_data_size)
        
        if len(packet) < offset + lap_data_size:
            return None
            
        data = struct.unpack(lap_data_fmt, packet[offset:offset+lap_data_size])
        
        return {
            'last_lap_time': data[0],
            'current_lap_time': data[1],
            'sector1_time': data[2],
            'sector2_time': data[3],
            'lap_distance': data[4],
            'total_distance': data[5],
            'car_position': data[7],
            'current_lap': data[8],
            'pit_status': data[9],
            'sector': data[11],
            'current_lap_invalid': data[12],
            'penalties': data[13]
        }

    @staticmethod
    def parse_session_data(packet):
        """
        Parse Session Data (ID 1)
        Extracts weather, track temperature, session type, etc.
        """
        header_fmt = '<HBBBBBQ fIIBB'
        header_size = struct.calcsize(header_fmt)
        
        # Session packet structure (simplified for key fields)
        # Format: B(Weather), B(TrackTemp), B(AirTemp), B(TotalLaps), H(SessionTime), B(SessionType), B(TrackID), B(Formula)
        session_fmt = '<BBBBHBBBxxxxxxxxx'  # x = padding for unused fields
        session_size = struct.calcsize(session_fmt)
        
        offset = header_size
        
        if len(packet) < offset + session_size:
            return None
        
        try:
            data = struct.unpack(session_fmt, packet[offset:offset+session_size])
            
            return {
                'weather': data[0],
                'track_temperature': data[1],
                'air_temperature': data[2],
                'total_laps': data[3],
                'session_time_left': data[4],
                'session_type': data[5],
                'track_id': data[6],
                'formula': data[7]
            }
        except struct.error:
            return None

    @staticmethod
    def parse_car_status(packet, player_index):
        """
        Parse Car Status Data (ID 7).
        Extracts tyre compound, tyre age, fuel in tank, and fuel remaining laps.

        Per-car struct (F1 2023/24 spec):
          B  tractionControl
          B  antiLockBrakes
          B  fuelMix
          B  frontBrakeBias
          B  pitLimiterStatus
          f  fuelInTank
          f  fuelCapacity
          f  fuelRemainingLaps
          H  maxRPM
          H  idleRPM
          B  maxGears
          B  drsAllowed
          H  drsActivationDistance
          B  actualTyreCompound
          B  visualTyreCompound
          B  tyresAgeLaps
          b  vehicleFiaFlags  (signed)
          f  enginePowerICE
          f  enginePowerMGUK
          f  ersStoreEnergy
          B  ersDeployMode
          f  ersHarvestedThisLapMGUK
          f  ersHarvestedThisLapMGUH
          f  ersDeployedThisLap
          B  networkPaused
        Total: 55 bytes per car
        """
        header_fmt  = '<HBBBBQfIIBB'
        header_size = struct.calcsize(header_fmt)

        car_fmt  = '<BBBBBfffHHBBHBBBbfffBfffB'
        car_size = struct.calcsize(car_fmt)   # 55 bytes

        offset = header_size + (player_index * car_size)
        if len(packet) < offset + car_size:
            return None

        try:
            d = struct.unpack(car_fmt, packet[offset:offset + car_size])
            return {
                'fuel_in_tank':          d[5],
                'fuel_remaining_laps':   d[7],
                'tyre_actual_compound':  d[13],
                'tyre_visual_compound':  d[14],
                'tyre_age_laps':         d[15],
            }
        except struct.error:
            return None


class UdpListener(threading.Thread):
    def __init__(self):
        super(UdpListener, self).__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.daemon = True
        
    def run(self):
        self.running = True
        try:
            # Allow address reuse to prevent "Address already in use" errors on restart
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((UDP_IP, UDP_PORT))
            logger.info(f"UDP Listener started on port {UDP_PORT}")
            
            while self.running:
                try:
                    data, _ = self.sock.recvfrom(BUFFER_SIZE)
                    # Parse Header first to get ID and Player Index
                    # Parse Header first to get ID and Player Index
                    # F1 24 Header Format with Overall Frame ID and Secondary Player Index
                    header_fmt = '<HBBBBQfIIBB' 
                    header_size = struct.calcsize(header_fmt)
                    
                    if len(data) < header_size:
                        continue
                        
                    # Unpack header
                    header_raw = struct.unpack(header_fmt, data[:header_size])
                    packet_id = header_raw[4]
                    player_index = header_raw[9] # Index 9 in new format (was 8)
                    
                    # Dispatch based on packet type
                    if packet_id == PACKET_ID_CAR_TELEMETRY:
                        result = F1PacketParser.parse_car_telemetry(data, player_index)
                        if result:
                            state.update_telemetry(result)
                            
                    elif packet_id == PACKET_ID_LAP_DATA:
                        result = F1PacketParser.parse_lap_data(data, player_index)
                        if result:
                            state.update_lap_data(result)
                            
                    elif packet_id == PACKET_ID_SESSION:
                        # Complete session packet parsing
                        result = F1PacketParser.parse_session_data(data)
                        if result:
                            state.update_session(result)

                    elif packet_id == PACKET_ID_CAR_STATUS:
                        result = F1PacketParser.parse_car_status(data, player_index)
                        if result:
                            state.update_telemetry(result)

                    logger.info(result)
                except struct.error as se:
                    logger.warning(f"Packet Struct Error: {se} (ID: {packet_id if 'packet_id' in locals() else 'Unknown'})")
                except Exception as e:
                    logger.error(f"Error handling packet ID {packet_id if 'packet_id' in locals() else 'Unknown'}: {e}")
                    
        except Exception as e:
            logger.critical(f"FATAL UDP Listener Error: {e}")
        finally:
            logger.info("UDP Listener stopping...")
            self.sock.close()
            
    def stop(self):
        self.running = False

if __name__ == '__main__':
    Listener = UdpListener()
    Listener.run()
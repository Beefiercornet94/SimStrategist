print('This will be the F1 Telemetry Server')

"""
F1 24 UDP Client
Handles receiving and parsing binary UDP packets from the F1 game.
Specific to F1 23/24 Packet Format (2023 Spec).
"""
import argparse
import os
import socket
import struct
import threading
import time
import logging
from f1.telemetry_state import state

# Recording constants (shared with recorder.py / replayer.py)
_REC_MAGIC = b'F1REC\x00'
_REC_VERSION = 1
_REC_HEADER_SIZE = 16
_REC_PKT_HDR_FMT = '<dH'

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
    def parse_car_telemetry(packet, player_index, header_size=None):
        """Parse Car Telemetry Data (ID 6)"""
        if header_size is None:
            header_size = struct.calcsize('<HBBBBQfIIBB')
        
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
    def parse_lap_data(packet, player_index, header_size=None):
        """Parse Lap Data (ID 2)"""
        if header_size is None:
            header_size = struct.calcsize('<HBBBBQfIIBB')
        
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
    def parse_session_data(packet, header_size=None):
        """
        Parse Session Data (ID 1)
        Extracts weather, track temperature, session type, etc.
        """
        if header_size is None:
            header_size = struct.calcsize('<HBBBBQfIIBB')
        
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
    def parse_car_status(packet, player_index, header_size=None):
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
        if header_size is None:
            header_size = struct.calcsize('<HBBBBQfIIBB')

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
    def __init__(self, record_to: str = None):
        """
        :param record_to: Optional path to a .f1rec file. When set, all raw UDP
                          packets are saved to this file alongside normal processing.
        """
        super(UdpListener, self).__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False
        self.daemon = True
        self._record_to = record_to
        self._rec_file = None
        self._rec_start = None
        self._rec_lock = threading.Lock()

    def _open_recording(self):
        path = self._record_to
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        f = open(path, 'wb')
        # 16-byte file header: 6-byte magic + 1-byte version + 9 reserved bytes
        f.write(_REC_MAGIC + bytes([_REC_VERSION]) + b'\x00' * 9)
        logger.info(f"Recording packets to {path!r}")
        return f

    def _write_packet(self, data: bytes):
        # Save the raw datagram (not the parsed dict) so replayer.py can run the
        # full parsing pipeline and catch any future parser bugs during replay.
        now = time.monotonic()
        if self._rec_start is None:
            self._rec_start = now
        elapsed = now - self._rec_start
        self._rec_file.write(struct.pack(_REC_PKT_HDR_FMT, elapsed, len(data)))
        self._rec_file.write(data)

    def start_recording(self, path: str) -> None:
        """Begin writing incoming UDP packets to *path* (.f1rec format)."""
        with self._rec_lock:
            if self._rec_file:
                return  # already recording
            self._record_to = path
            self._rec_start = None
            self._rec_file = self._open_recording()

    def stop_recording(self) -> None:
        """Flush and close the current recording file."""
        with self._rec_lock:
            if self._rec_file:
                self._rec_file.flush()
                self._rec_file.close()
                self._rec_file = None
                logger.info(f"Recording closed: {self._record_to!r}")
                self._record_to = None
                self._rec_start = None

    @property
    def is_recording(self) -> bool:
        return self._rec_file is not None

    @property
    def recording_path(self) -> str | None:
        return self._record_to

    def run(self):
        self.running = True
        if self._record_to:
            self._rec_file = self._open_recording()
        try:
            # Allow address reuse to prevent "Address already in use" errors on restart
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((UDP_IP, UDP_PORT))
            logger.info(f"UDP Listener started on port {UDP_PORT}")

            pkt_count = 0
            while self.running:
                try:
                    data, _ = self.sock.recvfrom(BUFFER_SIZE)

                    with self._rec_lock:
                        if self._rec_file:
                            self._write_packet(data)
                            pkt_count += 1
                            if pkt_count % 500 == 0:
                                self._rec_file.flush()

                    # Detect game generation from packet_format (first 2 bytes)
                    if len(data) < 2:
                        continue
                    packet_format = struct.unpack_from('<H', data, 0)[0]

                    if packet_format >= 2022:
                        # Gen 5 (F1 2022-2024): added overall_frame_id + secondary_player_car_index
                        header_fmt = '<HBBBBQfIIBB'
                        player_idx_pos = 9
                    elif packet_format >= 2018:
                        # Gen 2-4 (F1 2018-2021): original modern header, no overall_frame_id
                        header_fmt = '<HBBBBQfIB'
                        player_idx_pos = 8
                    else:
                        # Gen 1 (F1 2017 legacy): not supported
                        logger.debug(f"Legacy packet format {packet_format} not supported, skipping")
                        continue

                    header_size = struct.calcsize(header_fmt)
                    if len(data) < header_size:
                        continue

                    header_raw = struct.unpack(header_fmt, data[:header_size])
                    packet_id = header_raw[4]
                    player_index = header_raw[player_idx_pos]

                    # Route each packet type to its parser; other packet IDs are ignored
                    if packet_id == PACKET_ID_CAR_TELEMETRY:
                        result = F1PacketParser.parse_car_telemetry(data, player_index, header_size)
                        if result:
                            state.update_telemetry(result)

                    elif packet_id == PACKET_ID_LAP_DATA:
                        result = F1PacketParser.parse_lap_data(data, player_index, header_size)
                        if result:
                            state.update_lap_data(result)

                    elif packet_id == PACKET_ID_SESSION:
                        result = F1PacketParser.parse_session_data(data, header_size)
                        if result:
                            state.update_session(result)

                    elif packet_id == PACKET_ID_CAR_STATUS:
                        result = F1PacketParser.parse_car_status(data, player_index, header_size)
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
            if self._rec_file:
                self._rec_file.close()
                logger.info(f"Recording closed: {self._record_to!r}")

    def stop(self):
        self.running = False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='F1 UDP telemetry listener')
    parser.add_argument('--record', metavar='FILE',
                        help='Also save raw packets to a .f1rec file (e.g. example-data/session.f1rec)')
    args = parser.parse_args()

    listener = UdpListener(record_to=args.record)
    listener.run()
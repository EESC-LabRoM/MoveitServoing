
"use strict";

let MasterboardDataMsg = require('./MasterboardDataMsg.js');
let IOStates = require('./IOStates.js');
let RobotStateRTMsg = require('./RobotStateRTMsg.js');
let Analog = require('./Analog.js');
let RobotModeDataMsg = require('./RobotModeDataMsg.js');
let ToolDataMsg = require('./ToolDataMsg.js');
let Digital = require('./Digital.js');

module.exports = {
  MasterboardDataMsg: MasterboardDataMsg,
  IOStates: IOStates,
  RobotStateRTMsg: RobotStateRTMsg,
  Analog: Analog,
  RobotModeDataMsg: RobotModeDataMsg,
  ToolDataMsg: ToolDataMsg,
  Digital: Digital,
};

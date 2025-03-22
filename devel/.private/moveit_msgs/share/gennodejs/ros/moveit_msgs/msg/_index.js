
"use strict";

let MoveGroupActionFeedback = require('./MoveGroupActionFeedback.js');
let ExecuteTrajectoryFeedback = require('./ExecuteTrajectoryFeedback.js');
let MoveGroupSequenceAction = require('./MoveGroupSequenceAction.js');
let MoveGroupFeedback = require('./MoveGroupFeedback.js');
let ExecuteTrajectoryActionGoal = require('./ExecuteTrajectoryActionGoal.js');
let MoveGroupActionGoal = require('./MoveGroupActionGoal.js');
let MoveGroupSequenceFeedback = require('./MoveGroupSequenceFeedback.js');
let MoveGroupResult = require('./MoveGroupResult.js');
let MoveGroupSequenceResult = require('./MoveGroupSequenceResult.js');
let MoveGroupSequenceActionFeedback = require('./MoveGroupSequenceActionFeedback.js');
let ExecuteTrajectoryActionFeedback = require('./ExecuteTrajectoryActionFeedback.js');
let PlaceActionResult = require('./PlaceActionResult.js');
let ExecuteTrajectoryResult = require('./ExecuteTrajectoryResult.js');
let MoveGroupGoal = require('./MoveGroupGoal.js');
let PickupActionGoal = require('./PickupActionGoal.js');
let ExecuteTrajectoryAction = require('./ExecuteTrajectoryAction.js');
let MoveGroupActionResult = require('./MoveGroupActionResult.js');
let PickupActionFeedback = require('./PickupActionFeedback.js');
let PickupActionResult = require('./PickupActionResult.js');
let PlaceGoal = require('./PlaceGoal.js');
let PickupResult = require('./PickupResult.js');
let ExecuteTrajectoryActionResult = require('./ExecuteTrajectoryActionResult.js');
let PlaceFeedback = require('./PlaceFeedback.js');
let MoveGroupSequenceGoal = require('./MoveGroupSequenceGoal.js');
let ExecuteTrajectoryGoal = require('./ExecuteTrajectoryGoal.js');
let PlaceAction = require('./PlaceAction.js');
let PickupGoal = require('./PickupGoal.js');
let PickupFeedback = require('./PickupFeedback.js');
let MoveGroupAction = require('./MoveGroupAction.js');
let MoveGroupSequenceActionResult = require('./MoveGroupSequenceActionResult.js');
let PlaceActionFeedback = require('./PlaceActionFeedback.js');
let PlaceActionGoal = require('./PlaceActionGoal.js');
let PlaceResult = require('./PlaceResult.js');
let PickupAction = require('./PickupAction.js');
let MoveGroupSequenceActionGoal = require('./MoveGroupSequenceActionGoal.js');
let DisplayTrajectory = require('./DisplayTrajectory.js');
let MotionSequenceItem = require('./MotionSequenceItem.js');
let AttachedCollisionObject = require('./AttachedCollisionObject.js');
let ConstraintEvalResult = require('./ConstraintEvalResult.js');
let RobotState = require('./RobotState.js');
let AllowedCollisionMatrix = require('./AllowedCollisionMatrix.js');
let LinkPadding = require('./LinkPadding.js');
let Constraints = require('./Constraints.js');
let CartesianTrajectory = require('./CartesianTrajectory.js');
let RobotTrajectory = require('./RobotTrajectory.js');
let MotionPlanResponse = require('./MotionPlanResponse.js');
let ObjectColor = require('./ObjectColor.js');
let CollisionObject = require('./CollisionObject.js');
let BoundingVolume = require('./BoundingVolume.js');
let CartesianTrajectoryPoint = require('./CartesianTrajectoryPoint.js');
let KinematicSolverInfo = require('./KinematicSolverInfo.js');
let PlannerParams = require('./PlannerParams.js');
let ContactInformation = require('./ContactInformation.js');
let CartesianPoint = require('./CartesianPoint.js');
let VisibilityConstraint = require('./VisibilityConstraint.js');
let MoveItErrorCodes = require('./MoveItErrorCodes.js');
let OrientationConstraint = require('./OrientationConstraint.js');
let PositionIKRequest = require('./PositionIKRequest.js');
let GripperTranslation = require('./GripperTranslation.js');
let JointConstraint = require('./JointConstraint.js');
let CostSource = require('./CostSource.js');
let Grasp = require('./Grasp.js');
let MotionSequenceResponse = require('./MotionSequenceResponse.js');
let WorkspaceParameters = require('./WorkspaceParameters.js');
let PlanningSceneComponents = require('./PlanningSceneComponents.js');
let AllowedCollisionEntry = require('./AllowedCollisionEntry.js');
let PlanningScene = require('./PlanningScene.js');
let PlanningOptions = require('./PlanningOptions.js');
let MotionSequenceRequest = require('./MotionSequenceRequest.js');
let TrajectoryConstraints = require('./TrajectoryConstraints.js');
let PlaceLocation = require('./PlaceLocation.js');
let PlanningSceneWorld = require('./PlanningSceneWorld.js');
let LinkScale = require('./LinkScale.js');
let JointLimits = require('./JointLimits.js');
let PositionConstraint = require('./PositionConstraint.js');
let OrientedBoundingBox = require('./OrientedBoundingBox.js');
let DisplayRobotState = require('./DisplayRobotState.js');
let PlannerInterfaceDescription = require('./PlannerInterfaceDescription.js');
let GenericTrajectory = require('./GenericTrajectory.js');
let MotionPlanRequest = require('./MotionPlanRequest.js');
let MotionPlanDetailedResponse = require('./MotionPlanDetailedResponse.js');

module.exports = {
  MoveGroupActionFeedback: MoveGroupActionFeedback,
  ExecuteTrajectoryFeedback: ExecuteTrajectoryFeedback,
  MoveGroupSequenceAction: MoveGroupSequenceAction,
  MoveGroupFeedback: MoveGroupFeedback,
  ExecuteTrajectoryActionGoal: ExecuteTrajectoryActionGoal,
  MoveGroupActionGoal: MoveGroupActionGoal,
  MoveGroupSequenceFeedback: MoveGroupSequenceFeedback,
  MoveGroupResult: MoveGroupResult,
  MoveGroupSequenceResult: MoveGroupSequenceResult,
  MoveGroupSequenceActionFeedback: MoveGroupSequenceActionFeedback,
  ExecuteTrajectoryActionFeedback: ExecuteTrajectoryActionFeedback,
  PlaceActionResult: PlaceActionResult,
  ExecuteTrajectoryResult: ExecuteTrajectoryResult,
  MoveGroupGoal: MoveGroupGoal,
  PickupActionGoal: PickupActionGoal,
  ExecuteTrajectoryAction: ExecuteTrajectoryAction,
  MoveGroupActionResult: MoveGroupActionResult,
  PickupActionFeedback: PickupActionFeedback,
  PickupActionResult: PickupActionResult,
  PlaceGoal: PlaceGoal,
  PickupResult: PickupResult,
  ExecuteTrajectoryActionResult: ExecuteTrajectoryActionResult,
  PlaceFeedback: PlaceFeedback,
  MoveGroupSequenceGoal: MoveGroupSequenceGoal,
  ExecuteTrajectoryGoal: ExecuteTrajectoryGoal,
  PlaceAction: PlaceAction,
  PickupGoal: PickupGoal,
  PickupFeedback: PickupFeedback,
  MoveGroupAction: MoveGroupAction,
  MoveGroupSequenceActionResult: MoveGroupSequenceActionResult,
  PlaceActionFeedback: PlaceActionFeedback,
  PlaceActionGoal: PlaceActionGoal,
  PlaceResult: PlaceResult,
  PickupAction: PickupAction,
  MoveGroupSequenceActionGoal: MoveGroupSequenceActionGoal,
  DisplayTrajectory: DisplayTrajectory,
  MotionSequenceItem: MotionSequenceItem,
  AttachedCollisionObject: AttachedCollisionObject,
  ConstraintEvalResult: ConstraintEvalResult,
  RobotState: RobotState,
  AllowedCollisionMatrix: AllowedCollisionMatrix,
  LinkPadding: LinkPadding,
  Constraints: Constraints,
  CartesianTrajectory: CartesianTrajectory,
  RobotTrajectory: RobotTrajectory,
  MotionPlanResponse: MotionPlanResponse,
  ObjectColor: ObjectColor,
  CollisionObject: CollisionObject,
  BoundingVolume: BoundingVolume,
  CartesianTrajectoryPoint: CartesianTrajectoryPoint,
  KinematicSolverInfo: KinematicSolverInfo,
  PlannerParams: PlannerParams,
  ContactInformation: ContactInformation,
  CartesianPoint: CartesianPoint,
  VisibilityConstraint: VisibilityConstraint,
  MoveItErrorCodes: MoveItErrorCodes,
  OrientationConstraint: OrientationConstraint,
  PositionIKRequest: PositionIKRequest,
  GripperTranslation: GripperTranslation,
  JointConstraint: JointConstraint,
  CostSource: CostSource,
  Grasp: Grasp,
  MotionSequenceResponse: MotionSequenceResponse,
  WorkspaceParameters: WorkspaceParameters,
  PlanningSceneComponents: PlanningSceneComponents,
  AllowedCollisionEntry: AllowedCollisionEntry,
  PlanningScene: PlanningScene,
  PlanningOptions: PlanningOptions,
  MotionSequenceRequest: MotionSequenceRequest,
  TrajectoryConstraints: TrajectoryConstraints,
  PlaceLocation: PlaceLocation,
  PlanningSceneWorld: PlanningSceneWorld,
  LinkScale: LinkScale,
  JointLimits: JointLimits,
  PositionConstraint: PositionConstraint,
  OrientedBoundingBox: OrientedBoundingBox,
  DisplayRobotState: DisplayRobotState,
  PlannerInterfaceDescription: PlannerInterfaceDescription,
  GenericTrajectory: GenericTrajectory,
  MotionPlanRequest: MotionPlanRequest,
  MotionPlanDetailedResponse: MotionPlanDetailedResponse,
};

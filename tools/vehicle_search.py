"""为已存在的正向车型搜索添加段位起点反查，不改变正向识别模板。"""
import copy


def swipe_timing():
    """两向搜索共用时序；保留 400 像素步长，减少每步等待。"""
    return {"duration": 320, "pre_delay": 0, "post_delay": 350}


def add_reverse_search(pipeline, click, forward, list_guard, anchor_guard, anchor_target):
    prefix = forward + "_反查"
    entry, anchor, confirmed, found, swipe, stopped = [
        prefix + suffix for suffix in ["入口", "定位起点", "起点已确认", "点击车型", "滑动", "未找到_测试停止"]
    ]
    pipeline[anchor] = {**copy.deepcopy(list_guard), "action": "Click", "target": anchor_target,
                        "max_hit": 1, "post_delay": 1500, "timeout": 60000, "next": [confirmed]}
    pipeline[confirmed] = {**copy.deepcopy(anchor_guard), "action": "DoNothing",
                           "timeout": 60000, "max_hit": 1, "next": [found, swipe, stopped]}
    pipeline[found] = copy.deepcopy(pipeline[click])
    pipeline[found]["all_of"][1] = copy.deepcopy(list_guard)
    pipeline[swipe] = {**copy.deepcopy(list_guard), "action": "Swipe", "begin": [600, 420],
                       "end": [1000, 420], **swipe_timing(),
                       "max_hit": 24, "timeout": 60000, "next": [found, swipe, stopped]}
    pipeline[stopped] = {**copy.deepcopy(list_guard), "action": "DoNothing", "next": []}
    pipeline[entry] = {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                       "next": [anchor]}
    for node in pipeline.values():
        if node.get("next") == [click, forward]:
            node["next"] = [click, forward, anchor]
    return entry, confirmed, found, swipe, stopped

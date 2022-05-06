function fetchPollResult() {
	// note: link should be in config
	// i'll find out later about this
	$.get("http://localhost:9000/polls/active", function(data) {
		refreshPoll(data);
		refreshCounter(data);

		setTimeout(function () {
			fetchPollResult(data);
		}, 5000); //config.refreshInternalInMs);
	});
}

function refreshPoll(data) {
	$(".countryVote").remove()
	$("#question").html(data.question)
	
	const imgLink = {
		"yes"     : "./webpage/asset/yes.png",
		"no"      : "./webpage/asset/no.png",
		"abstain" : "./webpage/asset/abstain.png",
		"none"    : "./webpage/asset/abstain.png"
	};

	var column = 10;
	var index = 0;
	var $result = $("#result");
	for(var key in data.votes) {
		if(!data.votes.hasOwnProperty(key)) {
			continue;
		}

		var img = '<img class="align-self-center mr-3" src="' + imgLink[data.votes[key]] + '" width="30px" height="30px">'
		var country = '<div class="align-self-center media-body"><h3>' + key + '</h3></div>'

		var $countryVote = $('<div class="media countryVote"></div>');
		$countryVote.append(img)
		$countryVote.append(country)
		$result.append($countryVote);
		
	}
}

function refreshCounter(data) {
	counter = {
		"yes"     : 0,
		"no"      : 0,
		"abstain" : 0,
		"none"	  : 0
	};

	statement = {
		"yes"     : "In Favour",
		"no"      : "Against",
		"abstain" : "Abstention",
		"none"    : "none"
	};

	for(var key in data.votes) {
		if(!data.votes.hasOwnProperty(key)) {
			continue;
		}
		counter[data.votes[key]]++;
	}

	for(var key in counter) {
		var elementID = `#${key}Count`;
		$(elementID).html(`${statement[key]} : ${counter[key]}`);
	}
}

function fetchDateTime() {
	$("#currentDate").html(getDate());
	$("#currentTime").html(getTime());

	setTimeout(function() {
		fetchDateTime();
	}, 1000);
}

function getDate() {
	var today = new Date();
	return today.getDate() + '-' 
	       + (today.getMonth() + 1) + '-'
		   + today.getYear();
}

function getTime() {
	var time = new Date();
	return time.getHours() + ':'
	       + time.getMinutes() + ':'
		   + time.getSeconds();
}